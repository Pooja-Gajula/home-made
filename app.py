from flask import Flask, render_template, request, redirect, url_for, session
import boto3
import smtplib
import logging
from email.mime.text import MIMEText
from datetime import datetime
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
import os

# -------------------- Config --------------------

app = Flask(__name__)
app.secret_key = 'simple_secure_key_9472'

# AWS Configuration
AWS_REGION = 'ap-south-1'
DYNAMODB_TABLE = 'PickleOrders'

# Email settings
EMAIL_HOST = 'smtp.gajulapoojacsd@gmail.com'
EMAIL_PORT = 587
EMAIL_USER = 'gajulapoojacsd@gmail.com'
EMAIL_PASSWORD = "ppjk mhvg pcly ztcf"

# -------------------- Logger Setup --------------------

log_folder = 'logs'
log_file = os.path.join(log_folder, 'app.log')

if os.path.exists(log_folder):
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
else:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

logger = logging.getLogger(__name__)

# -------------------- AWS Setup --------------------

dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
orders_table = dynamodb.Table(DYNAMODB_TABLE)

# SNS Setup
sns = boto3.client('sns', region_name=AWS_REGION)

# -------------------- Helper Functions --------------------

def send_order_email(to_email, order_summary):
    try:
        msg = MIMEText(order_summary)
        msg['Subject'] = 'Your Order Confirmation'
        msg['From'] = EMAIL_USER
        msg['To'] = to_email

        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)

        logger.info("Order email sent to %s", to_email)
    except Exception as e:
        logger.error("Failed to send email: %s", e)

def save_order_to_dynamodb(order_data):
    try:
        orders_table.put_item(Item=order_data)
        logger.info("Order saved to DynamoDB: %s", order_data['order_id'])
    except Exception as e:
        logger.error("DynamoDB error: %s", e)

def send_sns_notification(message, phone_number=None, topic_arn=None):
    try:
        if phone_number:
            sns.publish(PhoneNumber=phone_number, Message=message)
            logger.info(f"SNS SMS sent to {phone_number}")
        elif topic_arn:
            sns.publish(TopicArn=topic_arn, Message=message)
            logger.info(f"SNS message published to topic {topic_arn}")
        else:
            logger.info("SNS notification skipped (no phone number or topic)")
    except Exception as e:
        logger.error("SNS send failed: %s", e)

# -------------------- Routes --------------------

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/products')
def products():
    return render_template('products.html')

@app.route('/veg_pickles')
def veg_pickles():
    return render_template('veg_pickles.html')

@app.route('/non_veg_pickles')
def non_veg_pickles():
    return render_template('non_veg_pickles.html')

@app.route('/snacks')
def snacks():
    return render_template('snacks.html')

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    product = request.form['product']
    price = float(request.form['price'])
    quantity = int(request.form.get('quantity', 1))

    cart = session.get('cart', [])

    for item in cart:
        if item['product'] == product:
            item['quantity'] += quantity
            break
    else:
        cart.append({'product': product, 'price': price, 'quantity': quantity})

    session['cart'] = cart
    logger.info("Added to cart: %s (x%d)", product, quantity)
    return redirect(url_for('cart'))

@app.route('/cart')
def cart():
    cart = session.get('cart', [])
    grand_total = sum(item['price'] * item['quantity'] for item in cart)
    return render_template('cart.html', cart=cart, grand_total=grand_total)

@app.route('/clear_cart', methods=['POST'])
def clear_cart():
    session.pop('cart', None)
    logger.info("Cart cleared.")
    return redirect(url_for('cart'))

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart = session.get('cart', [])
    if not cart:
        return redirect(url_for('cart'))

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        address = request.form['address']
        order_id = str(uuid.uuid4())
        order_time = datetime.now().isoformat()
        grand_total = sum(item['price'] * item['quantity'] for item in cart)

        order_data = {
            'order_id': order_id,
            'name': name,
            'email': email,
            'address': address,
            'order_time': order_time,
            'items': cart,
            'total': grand_total
        }

        save_order_to_dynamodb(order_data)

        summary = f"Order ID: {order_id}\nName: {name}\nTotal: ₹{grand_total}\n\nThank you for your order!"
        send_order_email(email, summary)

        # (Optional) SNS call is defined but not triggered here
        # send_sns_notification("New order received.")

        session.pop('cart', None)
        logger.info("Order placed and cart cleared.")
        return redirect(url_for('order_success'))

    grand_total = sum(item['price'] * item['quantity'] for item in cart)
    return render_template('checkout.html', cart=cart, grand_total=grand_total)

@app.route('/order_success')
def order_success():
    return render_template('order_success.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']
        full_message = f"New Contact Message:\n\nFrom: {name} <{email}>\n\nMessage:\n{message}"
        return render_template('contact.html', success=True)

    return render_template('contact.html')

# -------------------- Auth --------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    message = ''
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        response = users_table.get_item(Key={'username': username})
        user = response.get('Item')

        if user and check_password_hash(user['password'], password):
            session['username'] = username
            return redirect(url_for('home'))
        else:
            message = "Invalid username or password."

    return render_template('login.html', message=message)

@app.route('/signup', methods=['GET'])
def signup_page():
    return render_template('signup.html')

@app.route('/signup', methods=['POST'])
def signup():
    username = request.form['username']
    email = request.form['email']
    password = request.form['password']

    existing_user = users_table.get_item(Key={'username': username})
    if 'Item' in existing_user:
        return render_template('signup.html', message="Username already exists.")

    hashed_password = generate_password_hash(password)
    users_table.put_item(Item={
        'username': username,
        'email': email,
        'password': hashed_password
    })

    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    return render_template('logout.html')

# -------------------- Error Pages --------------------

@app.errorhandler(404)
def not_found_error(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(e):
    return render_template('500.html'), 500

# -------------------- Run App --------------------

if __name__ == '__main__':
    app.run(host='0.0.0.0',port=5000,debug=True)
