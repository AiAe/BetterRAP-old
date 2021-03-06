from flask import Flask, make_response, redirect, request, render_template, url_for, flash
import requests
import re
import datetime
from datetime import datetime as dt
import json
from flask_mail import Mail, Message
from helpers import mysql, API

with open("config.json", "r") as f:
    config = json.load(f)

with open("email.json", "r") as f:
    config_email = json.load(f)

with open("drafts.json", "r") as f:
    draft = json.load(f)

with open("ripple.json", "r") as f:
    ripple_config = json.load(f)

app = Flask(__name__)
app.secret_key = 'idkwhattowriteherebutthisisneededforflashsoo'

app.config['MAIL_SERVER'] = config_email['MAIL_SERVER']
app.config['MAIL_PORT'] = "7337"
app.config['MAIL_USERNAME'] = config_email['MAIL_USERNAME']
app.config['MAIL_PASSWORD'] = config_email['MAIL_PASSWORD']
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_DEFAULT_SENDER'] = config_email['MAIL_USERNAME']
app.config['MAIL_DEBUG'] = False

mail = Mail()
mail.init_app(app)


def rtheme():

    if request.cookies.get('cflags') == 1 or request.cookies.get('cflags') == "1":

        return {'theme': 'ds', 'logo': 'white', 'css': 'css/semantic.min.dark.css', 'header': 'img/logo-pink-dark.svg'}

    return {'theme': '', 'logo': 'black', 'css': 'css/semantic.min.white.css', 'header': 'img/logo-blue.svg'}


def send_email(email, d):
    if d == 0:
        text = draft['accept_appeal_cheating']
    elif d == 1:
        text = draft['accept_appeal_multi']
    elif d == 2:
        text = draft['accept_username']
    elif d == 3:
        text = draft['deny_appeal_multi']
    elif d == 4:
        text = draft['deny_appeal']
    elif d == 5:
        text = draft['deny_username']

    list = []
    list.append(email)

    msg = Message('Ripple Support', recipients=list)
    msg.body = text
    mail.send(msg)


@app.route('/oauth/ripple/')
def ripple_oauth():
    if not request.args:
        return 'I love hackers'

    data = {
        'client_id': ripple_config['client_id'],
        'client_secret': ripple_config['client_secret'],
        'grant_type': 'authorization_code',
        'code': request.args['code'],
    }

    ripple_token = requests.post("https://ripple.moe/oauth/token", data=data).json()

    headers = {'Authorization': 'Bearer ' + ripple_token['access_token']}

    user = requests.get('https://ripple.moe/api/v1/users/self', headers=headers).json()

    expire_date = datetime.datetime.now()
    expire_date = expire_date + datetime.timedelta(days=1)

    red = make_response(redirect('/'))
    red.set_cookie('ACCESS_TOKEN', ripple_token['access_token'], expires=expire_date)

    connection, cursor = mysql.connect()

    try:
        mysql.execute(connection, cursor,
                      "INSERT INTO users (user_id, access_token) VALUES (%s, %s)",
                      [user['id'], ripple_token['access_token']])
    except:
        mysql.execute(connection, cursor,
                      "UPDATE users SET access_token = %s WHERE user_id = %s",
                      [ripple_token['access_token'], user['id']])

    return red


@app.route('/oauth/ripple/logout/')
def ripple_logout():
    if API.user_logged_in():
        access_token = request.cookies.get('ACCESS_TOKEN')

        headers = {'Authorization': 'Bearer ' + access_token}

        requests.post('https://ripple.moe/api/v1/tokens/self/delete',
                      headers=headers).json()

        red = make_response(redirect(url_for('index')))
        red.set_cookie('ACCESS_TOKEN', '', expires=0)
        return red
    else:

        return 'Gotta love hackers...'


@app.route('/')
def index():
    if API.user_logged_in():
        return redirect(url_for('home'))

    return render_template('login.html', client_id=ripple_config['client_id'],
                           redirect_url=ripple_config['redirect_url'], rtheme=rtheme())


@app.route('/home/')
def home():
    if not API.user_logged_in():
        return redirect(url_for('index'))

    user_id = API.api_user_username(API.user_exist()['user_id'])
    user_privilege = API.user_privilege()

    return render_template('home.html', user=user_id, user_privilege=user_privilege, rtheme=rtheme())


@app.route('/action/')
def api_action():
    if not request.args:
        return 'I love hackers'

    user_id = request.args['user_id']

    if not API.user_in_db(user_id):
        return 'kys'

    params = {
        'token': ripple_config['token'],
    }

    action = int(request.args['action'])

    connection, cursor = mysql.connect()

    if action == 1 or action == 2:

        if not API.is_chatmod() or not API.user_in_db(user_id):
            return redirect(url_for('index'))

        # Name change approve
        if action == 1:
            json_data = {
                'id': int(request.args['user_id']),
                'username': str(request.args['username'])
            }

            user = API.api_user_edit(params, json_data)

            if user['code'] != 200 and user['message'] == "Can't edit that user":
                flash("Can't edit that user!")

            else:
                u = API.user_exist()
                username = API.api_user_username(u['user_id'])
                text = 'Changed username from {} to {}'.format(user["username"], request.args['username'])
                API.logging(username['username'], u["user_id"], text)
                mysql.execute(connection, cursor, "DELETE from requests WHERE user_id = %s", [user_id])
                get_email = API.api_user_full(user_id)["email"]

                try:
                    send_email(get_email, 2)
                except:
                    flash('Failed to send, email is not valid.')

                flash('Changed username from {} to {}.'.format(user["username"],
                                                               request.args['username']))

            return redirect(url_for('manage_usernamechanges'))

        # Name change deny
        elif action == 2:
            u = API.user_exist()
            username = API.api_user_username(u['user_id'])
            text = 'Deny username change from {} to {}'.format(request.args['u'], request.args['username'])
            API.logging(username['username'], u["user_id"], text)
            mysql.execute(connection, cursor, "DELETE from requests WHERE user_id = %s", [user_id])
            get_email = API.api_user_full(user_id)["email"]

            try:
                send_email(get_email, 5)
            except:
                flash('Failed to send, email is not valid.')

            flash('Deny username change from {} to {}.'.format(request.args['u'], request.args['username']))

            return redirect(url_for('manage_usernamechanges'))
    else:
        if not API.is_admin():
            return redirect(url_for('index'))

        # Unrestrict approve
        if action == 3:

            json_data = {
                'user_id': int(request.args['user_id']),
                'allowed': 1
            }

            API.api_user_unrestrict(params, json_data)

            u = API.user_exist()
            username = API.api_user_username(u['user_id'])
            text = '{} is unrestricted'.format(request.args['username'])
            API.logging(username['username'], u["user_id"], text)
            mysql.execute(connection, cursor, "DELETE from requests WHERE user_id = %s", [user_id])
            get_email = API.api_user_full(user_id)["email"]

            try:
                send_email(get_email, 2)
            except:
                flash('Failed to send, email is not valid.')

            flash('{} is unrestricted'.format(request.args['user_id']))

            return redirect(url_for('manage_banappeals'))

        # Unrestrict deny
        elif action == 4:
            u = API.user_exist()
            username = API.api_user_username(u['user_id'])
            text = 'Deny appeal for {}'.format(request.args['username'])
            API.logging(username['username'], u["user_id"], text)
            mysql.execute(connection, cursor, "DELETE from requests WHERE user_id = %s", [user_id])
            get_email = API.api_user_full(user_id)["email"]

            try:
                send_email(get_email, 4)
            except:
                flash('Failed to send, email is not valid.')

            flash('Deny appeal for {}.'.format(request.args['username']))

            return redirect(url_for('manage_banappeals'))

    return 'kys'


@app.route('/banappeal/', methods=['GET', 'POST'])
def request_banappeal():
    if not API.user_logged_in() or not API.is_restricted():
        return redirect(url_for('index'))

    inputs = {'q1': "", 'q2': "", 'q3': "", 'q4': "", 'q5': "", 'q6': ""}

    user = API.api_user_username(API.user_exist()['user_id'])
    user_privilege = API.user_privilege()

    if request.method == 'POST':

        inputs = {'q1': request.form['q1'], 'q2': request.form['q2'], 'q3': request.form['q3'],
                  'q4': request.form['q4'], 'q5': request.form['q5'], 'q6': request.form['q6']}

        if not all([inputs['q1'], inputs['q2'], inputs['q3'], inputs['q4'], inputs['q5'], inputs['q6']]):
            flash('Please fill everything!')
        else:
            text = "{q1}\n{q2}\n{q3}\n{q4}\n{q5}\n{q6}\n".format(**inputs)

            connection, cursor = mysql.connect()

            try:
                mysql.execute(connection, cursor,
                              "INSERT INTO requests (user_id, username, category, text, date) VALUES (%s, %s, %s, %s, %s)",
                              [user['id'], user['username'], 2, text,
                               dt.now().strftime('%d.%m.%Y %H:%M')])

                #flash('Thanks for appealing, it can take up to 7 days for us to review.')

            except:
                flash("I see you really want to get unrestricted, don't we will review your appeal soon.")

    return render_template('banappeal.html', user=user, user_privilege=user_privilege, fields=inputs,
                           db=API.user_in_db(user['id']), email=API.api_user_email(user['id']), rtheme=rtheme())


@app.route('/namechange/', methods=['GET', 'POST'])
def request_namechange():
    if not API.user_logged_in() or not API.is_user():
        return redirect(url_for('index'))

    user = API.api_user_username(API.user_exist()['user_id'])
    user_privilege = API.user_privilege()

    if request.method == 'POST':

        username = request.form['username']

        if not username:
            flash('Username is empty!')

        regex = r"^[A-Za-z0-9 _\[\]-]{2,15}$"

        if not re.match(regex, username):
            flash("Failed to verify username, please don't use special characters.")

        if API.api_user_check(username):
            flash("Username is in use!")

        if API.api_osu_user_check(username):
            used = 1

        else:
            used = 0

        if username and re.match(regex, username) and not API.api_user_check(username):
            connection, cursor = mysql.connect()
            try:
                mysql.execute(connection, cursor,
                              "INSERT INTO requests (user_id, username, category, used, new_username, date) VALUES (%s, %s, %s, %s, %s, %s)",
                              [user['id'], user['username'], 1, used,
                               username,
                               dt.now().strftime('%d.%m.%Y %H:%M')])
                #flash('Your request is added to pending.')
            except:
                flash('You have still pending username change!')

    return render_template('namechange.html', user=user, user_privilege=user_privilege, db=API.user_in_db(user['id']),
                           email=API.api_user_email(user['id']), rtheme=rtheme())


@app.route('/manage/usernamechanges/')
def manage_usernamechanges():
    if not API.user_logged_in() or not API.is_chatmod():
        return redirect(url_for('index'))

    user = API.api_user_username(API.user_exist()['user_id'])
    user_privilege = API.user_privilege()

    connection, cursor = mysql.connect()
    get_requests = mysql.execute(connection, cursor,
                                 "SELECT * FROM requests WHERE category = 1").fetchall()
    return render_template('manageusernamechanges.html', user=user, user_privilege=user_privilege, r=get_requests, rtheme=rtheme())


@app.route('/manage/banappeals/')
def manage_banappeals():
    if not API.user_logged_in() or not API.is_admin():
        return redirect(url_for('index'))

    user = API.api_user_username(API.user_exist()['user_id'])
    user_privilege = API.user_privilege()

    connection, cursor = mysql.connect()
    get_requests = mysql.execute(connection, cursor,
                                 "SELECT * FROM requests WHERE category = 2").fetchall()
    return render_template('managebanappeals.html', user=user, user_privilege=user_privilege, r=get_requests, rtheme=rtheme())


@app.route('/manage/read/')
def manage_read():
    if not API.user_logged_in() or not API.is_admin():
        return redirect(url_for('index'))

    if not request.args:
        return 'kys'

    user_id = request.args['user_id']

    user = API.api_user_username(API.user_exist()['user_id'])
    user_privilege = API.user_privilege()

    connection, cursor = mysql.connect()
    get_text = mysql.execute(connection, cursor,
                             "SELECT user_id, username, text FROM requests WHERE user_id = %s", [user_id]).fetchone()
    return render_template('read.html', user=user, user_privilege=user_privilege, r=get_text, rtheme=rtheme())


@app.route('/logs/')
def logs():
    if not API.user_logged_in() or not API.is_admin():
        return redirect(url_for('index'))

    user_id = API.api_user_username(API.user_exist()['user_id'])
    user_privilege = API.user_privilege()

    connection, cursor = mysql.connect()
    get_requests = mysql.execute(connection, cursor,
                                 "SELECT * FROM logs ORDER BY id desc").fetchall()
    return render_template('logs.html', user=user_id, user_privilege=user_privilege, r=get_requests, rtheme=rtheme())


@app.errorhandler(404)
def not_found(error):
    return '404'


if __name__ == "__main__":
    app.run(**config)
