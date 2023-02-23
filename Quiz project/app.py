from flask import Flask, redirect, url_for, session, request, render_template, jsonify
from flask_oauthlib.client import OAuth
from pymongo import MongoClient
from datetime import datetime


app = Flask(__name__)
app.secret_key = 'qquuiizzproject'
oauth = OAuth(app)

# DataBase connection
client = MongoClient("mongodb://localhost:27017/")
db = client['quiz']
user_collection = db["user_collection"]

quiz_name = 'Englishh'

now = datetime.now()
current_date = now.strftime("%Y-%m-%d")

date = current_date

google = oauth.remote_app(
    'google',
    consumer_key='123989450831-dh8bf80389vim7b67ucbmg6fc3qlvsji.apps.googleusercontent.com',
    consumer_secret='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',
    request_token_params={
        'scope': 'email profile'
    },
    base_url='https://www.googleapis.com/oauth2/v1/',
    request_token_url=None,
    access_token_method='POST',
    access_token_url='https://accounts.google.com/o/oauth2/token',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
)


def login_required(f):
    def wrapper(*args, **kwargs):
        if 'email' in session:
            return f(*args, **kwargs)
        else:
            return render_template('index.html', show_popup2=True)
    return wrapper


@app.route('/', methods=['POST', 'GET'])
def index():
    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]
        valid = user_collection.find_one(
            {"data.email": email, "data.password": password})

        if valid:
            session['email'] = email
            return redirect(url_for('home'))

        else:
            return render_template('index.html', show_popup1=True)

    return render_template("index.html", show_popup1=False, show_popup2=False, show_popup3=True)


@app.route('/login')
def login():
    if 'email' in session:
        email = session.get('email')
        user = user_collection.find_one({"data.email": email})
        if 'password' in user['data']:
            return redirect(url_for('home'))
        else:
            return redirect(url_for('password'))
    return redirect(url_for('callback'))


@app.route('/callback')
def callback():
    return google.authorize(callback=url_for('authorized', _external=True))


@app.route('/callback/authorized')
def authorized():
    resp = google.authorized_response()
    if resp is None:
        return 'Access denied: reason=%s error=%s' % (
            request.args['error_reason'],
            request.args['error_description']
        )
    session['google_token'] = (resp['access_token'], '')

    me = google.get('userinfo')
    email = me.data['email']
    session['email'] = email

    existed = user_collection.find_one({"data.email": email})

    if existed:
        return redirect(url_for('home'))
    else:
        user_collection.insert_one({'data': me.data})
        return redirect(url_for('password'))


@app.route('/password', methods=['POST', 'GET'], endpoint='password')
@login_required
def password():
    if request.method == 'POST':
        email = session.get('email')
        password = request.form['password2']
        user_collection.update_one({"data.email": email}, {
                                   "$set": {"data.password": password}})

        return redirect(url_for('home'))

    return render_template('password.html')


def get_user_details():
    email = session.get('email')
    details = user_collection.find_one({"data.email": email})
    name = details["data"]["name"]
    return {'email': email, 'name': name}


@app.route("/home", methods=['GET', 'POST'], endpoint='home')
@login_required
def home():
    user_details = get_user_details()
    quiz_taken = session.pop('quiz_taken', False)
    return render_template('home.html', user_details=user_details, quiz_taken=quiz_taken)


@app.route("/quiz", methods=['POST', 'GET'], endpoint='quiz')
@login_required
def quiz():
    email = session.get('email')
    already_written = user_collection.find_one({"data.email": email, "quiz_responses": {
                                               "$exists": True, "$ne": None}, f"quiz_responses.{date}.{quiz_name}": {"$exists": True}})

    if already_written:
        session['quiz_taken'] = True
        return redirect(url_for('home'))
    else:
        if request.method == 'POST':
            email = session.get('email')
            response_data = request.get_json()

            quiz_attempt = {
                "Time Used": response_data.get("Time_Used", ""),
                "Score": response_data.get("Score", "0 out of 5"),
                "Questions": response_data.get("Questions_Data", "")
            }

            user_collection.update_one(
                {"data.email": email},
                {"$set": {f"quiz_responses.{date}.{quiz_name}": quiz_attempt}})
            return jsonify()
        else:
            request.method == 'GET'
            user_details = get_user_details()
            return render_template('quiz.html', user_details=user_details, quiz_name=quiz_name)


@app.route("/report", methods=['GET', 'POST'], endpoint='report')
@login_required
def report():
    if request.method == 'POST':
        email = session.get('email')
        date = request.get_json()
        quiz_data = user_collection.find_one({"data.email": email}).get(
            "quiz_responses", {}).get(date, {})
        if not quiz_data:
            error = "data not found for the given date"
            return jsonify(error)
        else:
            return jsonify(quiz_data)

    else:
        request.method == 'GET'
        user_details = get_user_details()
        return render_template('report.html', user_details=user_details)


@app.route('/logout')
def logout():
    session.pop('google_token', None)
    session.clear()
    return redirect(url_for("index"))


@google.tokengetter
def get_google_oauth_token():
    return session.get('google_token')


if __name__ == "__main__":
    app.run(debug=True)
