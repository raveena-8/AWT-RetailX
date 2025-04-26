from flask import Flask, render_template, request, redirect, url_for, session, flash, render_template_string
import pyrebase
import firebase_admin
from firebase_admin import credentials, firestore
import datetime

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from firebase_admin import firestore,  auth
from flask import flash, redirect, url_for, request



app = Flask(__name__)
app.secret_key = 'your-secret-key'

# -------------------- Firebase Auth Config --------------------
firebase_config = {
    "apiKey": "AIzaSyCJnzCC_tJa0BcwGsKTr6mG9Z86QIhvvtw",
    "authDomain": "retailx-da9e3.firebaseapp.com",
    "projectId": "retailx-da9e3",
    "storageBucket": "retailx-da9e3.firebasestorage.app",
    "messagingSenderId": "951965803597",
    "appId": "1:951965803597:web:1d7d9bc07c999539ff2804",
    "databaseURL": "https://retailx-da9e3-default-rtdb.firebaseio.com/",
  };
firebase = pyrebase.initialize_app(firebase_config)
pyre_auth  = firebase.auth()

# -------------------- Firestore DB Config ---------------------
cred = credentials.Certificate("retailx-config.json")  # path to your downloaded key
firebase_admin.initialize_app(cred)
db = firestore.client()

# -------------------- Routes ----------------------


# Send email to user
def send_order_email(order_data):
    user_id = session.get('user')
    if not user_id:
        flash("Please log !!", 'info')
        return redirect(url_for('login'))
    user_email = session.get('email')  # User's email (could be from session)
    subject = "Order Confirmation"
    body = """
    Dear {name},

    Thank you for your order!

    Order Details:
    Shipping Address: {address}, {city} - {postal}
    Phone: {phone}
    Payment Method: {payment_method}
    
    Order Summary:
    {order_summary}

    Total: £{total}

    We will notify you once your order is shipped.

    Regards,
    RetailX
    """.format(
        name=order_data['name'],
        address=order_data['address'],
        city=order_data['city'],
        postal=order_data['postal'],
        phone=order_data['phone'],
        total=order_data['total'],
        payment_method=order_data['payment_method'],
        order_summary = "".join([
            f"{item['name']} - Qty: {item['quantity']} - Price: {item['price']}\n"
            for item in order_data['cart']
        ])
    )

    # body = "test"

    msg = MIMEMultipart()
    msg['From'] = "retailxiot@gmail.com"  # Sender's email
    msg['To'] = user_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    # Send the email via SMTP server
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login("retailxiot@gmail.com", "kebnyjmuqfhxuzgt")  # Your email credentials
        text = msg.as_string()
        server.sendmail("retailxiot@gmail.com", user_email, text)
        server.quit()
    except Exception as e:
        print(f"Error sending email: {e}")




# Home Route
@app.route('/')
def index():
    products_ref = db.collection('products').stream()
    products = []
    categories = set()  # Use a set to collect unique categories

    for doc in products_ref:
        product = doc.to_dict()
        product['id'] = doc.id
        products.append(product)

        # Collect unique categories
        if 'category' in product:
            categories.add(product['category'])

    return render_template('index.html', products=products, categories=sorted(categories))


@app.route('/product/<product_id>')
def product_page(product_id):


    try:
        product_ref = db.collection('products').document(product_id)
        product = product_ref.get()

        print("Product ID:", product_id)
        print("Exists:", product.exists)

        if product.exists:
            product_data = product.to_dict()
            product_data['id'] = product.id  # Just in case you need it on the page
            print(product_data)
            return render_template('product.html', product=product_data)

        else:
            print("error")
            flash('Product not found!', 'error')
            return redirect(url_for('index'))

    except Exception as e:
        flash(f'Error fetching product: {str(e)}', 'error')
        print(f'Error fetching product: {str(e)})')
        return redirect(url_for('index'))


# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        try:
            user = pyre_auth.sign_in_with_email_and_password(email, password)
            session['user'] = user['localId']  # Store user ID in session
            session['email'] = user['email']
            flash('Logged In', 'success')
            return redirect(url_for('index'))
        
        except:
            flash('Invalid credentials, please try again.', 'error')

    return render_template('login.html')

# Signup Route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        try:
            # Step 1: Create the user
            pyre_auth.create_user_with_email_and_password(email, password)

            # Step 2: Sign in the user right after signup
            user = pyre_auth.sign_in_with_email_and_password(email, password)

            # Step 3: Get uid and store session
            session['user'] = user['localId']
            session['email'] = email

            flash('Account created and signed in successfully!', 'success')
            return redirect(url_for('index'))

        except Exception as e:
            print(e)  # For debugging
            flash('An error occurred while creating your account. Please try again.', 'error')

    return render_template('signup.html')

@app.route('/cart')
def cart():
    user_id = session.get('user')
    if not user_id:
        flash("Please log in to view your cart.", 'info')
        return redirect(url_for('login'))

    try:
        cart_ref = db.collection('carts').document(user_id)
        cart_doc = cart_ref.get()
        cart_data = cart_doc.to_dict() if cart_doc.exists else {}

        cart_items = []
        total = 0

        for product_id, quantity in cart_data.items():
            product_ref = db.collection('products').document(product_id)
            product_doc = product_ref.get()
            if product_doc.exists:
                product = product_doc.to_dict()
                product['id'] = product_id
                product['quantity'] = quantity
                product['subtotal'] = product['price'] * quantity
                cart_items.append(product)
                total += product['subtotal']

        return render_template('cart.html', cart=cart_items, total=total)

    except Exception as e:
        flash(f"Error loading cart: {e}", 'error')
        return redirect(url_for('index'))


@app.route('/remove_from_cart/<product_id>', methods=['POST'])
def remove_from_cart(product_id):
    user_id = session.get('user')
    if not user_id:
        flash("Please log in.", 'info')
        return redirect(url_for('login'))

    try:
        cart_ref = db.collection('carts').document(user_id)
        cart_doc = cart_ref.get()
        cart = cart_doc.to_dict() if cart_doc.exists else {}

        if product_id in cart:
            del cart[product_id]
            cart_ref.set(cart)
            flash("Product removed from cart.", "success")
        else:
            flash("Product not found in cart.", "error")
    except Exception as e:
        flash(f"Error: {e}", "error")

    return redirect(url_for('cart'))



@app.route('/test-email')
def test_email():
    test_order_data = {
        'name': 'Test User',
        'address': '123 Test Street',
        'city': 'Testville',
        'postal': '123456',
        'phone': '9876543210',
        'payment_method': 'COD',
        'cart': {
            'test-product-1': {
                'name': 'Smart Sensor',
                'price': 999,
                'quantity': 2
            },
            'test-product-2': {
                'name': 'IoT Switch',
                'price': 499,
                'quantity': 1
            }
        },
        'total': 999 * 2 + 499
    }

    send_order_email(test_order_data)
    return 'Test email sent (check your inbox or terminal logs)'


@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    user_id = session.get('user')  # Use 'user' as the key for user ID
    if not user_id:
        flash("You must be logged in to proceed to checkout.", "info")
        return redirect(url_for('login'))

    try:
        # Retrieve the cart from Firebase
        cart_ref = db.collection('carts').document(user_id)
        cart_doc = cart_ref.get()
        if cart_doc.exists:
            cart = cart_doc.to_dict()
        else:
            cart = {}

        if not cart:
            flash("Your cart is empty", "info")
            return redirect(url_for('cart'))

        # Initialize variables
        cart_items = []
        total = 0

        # Loop through the cart to get product details
        for product_id, quantity in cart.items():
            product_ref = db.collection('products').document(product_id)
            product_doc = product_ref.get()

            if product_doc.exists:
                product = product_doc.to_dict()
                product['id'] = product_id
                product['quantity'] = quantity
                product['subtotal'] = product['price'] * quantity  # Calculate subtotal for the product
                cart_items.append(product)
                total += product['subtotal']  # Add subtotal to total

        if request.method == 'POST':
            # Collecting order information
            # Inside request.method == 'POST'
            order_data = {
                'name': request.form['name'],
                'address': request.form['address'],
                'city': request.form['city'],
                'postal': request.form['postal'],
                'phone': request.form['phone'],
                'payment_method': request.form.get('payment_method'),
                'order_date': datetime.datetime.now(),
                'cart': cart_items,
                'total': float(request.form.get('final_total', total)),  # use final_total from form if available
                'gift_card_applied': float(request.form.get('gift_card_value', 0)),
                'voucher_applied_percent': float(request.form.get('voucher_percent', 0)),
            }


            # Store the order in Firebase
            orders_ref = db.collection('orders')
            order_ref = orders_ref.add(order_data)
            print(order_data)
            # Send email to user
            send_order_email(order_data)

            # Clear cart after order is placed
            cart_ref.delete()  # Remove the cart from Firebase after order is placed
            flash('Order placed successfully!', 'success')
            return redirect(url_for('index'))

        # Render checkout page with cart items and total
        return render_template('checkout.html', cart=cart_items, total=total)

    except Exception as e:
        flash(f"Error retrieving cart: {e}", "error")
        return redirect(url_for('cart'))



# Admin Route - Add Product
@app.route('/admin/add-product', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        image = request.form['image']
        category = request.form['category']

        product_ref = db.collection('products').add({
            'name': name,
            'description': description,
            'price': price,
            'image': image,
            'category': category,
            'stock_status': request.form.get('stock_status', 'In Stock')
        })
        flash('Product added successfully!', 'success')
        return redirect(url_for('admin'))

    return render_template('admin.html')

@app.route('/add_to_cart/<product_id>', methods=['POST'])
def add_to_cart(product_id):
    user_id = session.get('user')
    if not user_id:
        flash("Login to check out!", "error")
        return redirect(url_for('login'))

    try:
        # ✅ Get product details to check stock
        product_ref = db.collection('products').document(product_id)
        product_doc = product_ref.get()

        if not product_doc.exists:
            flash("Product not found.", "error")
            return redirect(url_for('index'))

        product = product_doc.to_dict()
        if product.get('stock_status') != 'In Stock':
            flash("Sorry, this product is out of stock!", "error")
            return redirect(url_for('product_page', product_id=product_id))

        # ✅ Proceed with adding to cart
        cart_ref = db.collection('carts').document(user_id)
        cart_doc = cart_ref.get()
        cart = cart_doc.to_dict() if cart_doc.exists else {}

        # Add product or increment quantity
        if product_id in cart:
            cart[product_id] += 1
        else:
            cart[product_id] = 1

        cart_ref.set(cart)
        flash("Product added to cart!", "success")

    except Exception as e:
        flash(f'Error adding to cart: {e}', 'error')

    return redirect(url_for('product_page', product_id=product_id))


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # 🔒 Replace with your own admin credentials
        admin_email = 'admin@gmail.com'
        admin_password = 'admin'

        if email == admin_email and password == admin_password:
            session['admin'] = True
            flash('Admin logged in successfully!', 'success')
            return redirect(url_for('admin'))
        else:
            flash('Invalid admin credentials', 'error')

    return render_template('admin_login.html')




@app.route('/admin')
def admin():

    if not session.get('admin'):
        flash("Admin login required.", "warning")
        return redirect(url_for('admin_login'))
    total_orders = len(list(db.collection('orders').stream()))
    # Total users using Firebase Auth Admin SDK
    total_users = 0
    page = auth.list_users()

    while page:
        total_users += len(page.users)
        page = page.get_next_page()
    # Fetch products
    products_ref = db.collection('products')
    products = products_ref.stream()
    product_list = [{"id": p.id, **p.to_dict()} for p in products] 

    total_products = len(product_list)
    in_stock = sum(1 for p in product_list if p.get('stock_status') == 'In Stock')
    out_of_stock = sum(1 for p in product_list if p.get('stock_status') == 'Out of Stock')


    # Fetch orders
    orders_ref = db.collection('orders')
    orders = orders_ref.stream()
    order_list = []
    for order in orders:
        order_data = order.to_dict()
        order_data['id'] = order.id  # Add ID for reference
        order_list.append(order_data)

    return render_template('admin.html', products=product_list, orders=order_list, total_orders=total_orders,
                           total_users=total_users,
                           in_stock=in_stock,
                           out_of_stock=out_of_stock)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    flash('Admin logged out.', 'info')
    return redirect(url_for('index'))



@app.route('/admin/delete-product/<product_id>', methods=['POST'])
def delete_product(product_id):
    db.collection('products').document(product_id).delete()
    flash("Product deleted successfully!", "success")
    return redirect(url_for('admin'))

@app.route('/admin/edit-product/<product_id>', methods=['POST'])
def edit_product(product_id):
    data = {
        'name': request.form['name'],
        'description': request.form['description'],
        'price': float(request.form['price']),
        'image': request.form['image'],
        'category': request.form['category'],
        'stock_status': request.form['stock_status']
    }
    db.collection('products').document(product_id).update(data)
    flash("Product updated successfully!", "success")
    return redirect(url_for('admin'))

@app.route('/admin/delete-order/<order_id>', methods=['POST'])
def delete_order(order_id):
    try:
        db.collection('orders').document(order_id).delete()
        flash("Order deleted successfully.", "success")
    except Exception as e:
        flash(f"Error deleting order: {e}", "error")
    return redirect(url_for('admin'))



@app.route('/logout')
def logout():
    session.pop('user', None)  # Remove user from session
    flash('You have been logged out!', 'info')
    return redirect(url_for('index'))  # Redirect to home or login page


# Start the Flask application
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
