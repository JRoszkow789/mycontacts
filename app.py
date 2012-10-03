from __future__ import absolute_import
import MySQLdb
from flask import Flask, render_template, request, redirect, url_for, session, g, flash
from werkzeug import check_password_hash, generate_password_hash
from decorators import requires_login
import logging
import re


# Create Our Application Object
app = Flask(__name__)
app.config.from_object('config')


# RegEx objects for Validation
RE_EMAIL = re.compile(r'^\w+@\w+\.\w+$')
RE_PWORD = re.compile(r'^\w+$')


# Handle Database connections
def connect_db():
    """Returns a new connection to the app's database."""
    return MySQLdb.connect(
        host=app.config['DB_HOST'],
        port=app.config['DB_PORT'],
        user=app.config['DB_USER'],
        passwd=app.config['DB_PASS'],
        db=app.config['DATABASE']
    );


def query_db(query, args=(), one=True):
    cursor = connect_db().cursor()
    cursor.execute(query, args)
    rv = cursor.fetchone() if one else cursor.fetchall()
    return rv


def get_user_object(user_id):
    """Returns a dictionary for simple representation of a user.
       keys are 'user_id' and 'name'.
    """
    name = query_db(
        'select item from data where thing_id=%s and item_title=%s',
        (user_id, 'name'),
        one=True)
    if name is not None:
        name = ' '.join([x.capitalize() for x in name[0].split()])
    return dict(user_id=user_id, name=name)


def mycard_initialized(user_id):
    """Checks to see if a user has created their first mycard yet."""

    rv = query_db(
        'select item from data where thing_id=%s and item_title=%s',
        (user_id, 'mycard_initialized'), one=True)
    if rv is None:
        # Check to rule out false negatives
        user_phone = query_db(
            'select data_id from data where thing_id=%s and item_title=%s',
            (user_id, 'primary_phone'))
        if user_phone is not None:
            # FALSE NEGATIVE!
            app.logger.debug('false negative found for user_id: %s' %  user_id)
            g.db.cursor().execute(
                'insert into data values (%s, %s, %s, %s)',
                [None, user_id, 'mycard_initialized', 1])
            g.db.commit()
            return True
        # No False negatives, simply not initialized. Return False
        return False
    else:
        rv = rv[0]
        if rv != '1':
            app.logger.debug('Error in mycard_initialized. Value: %s' % rv)
            return False
    return True


def get_mycard_details(user_id):
    """Takes a users id as a parameter and returns their main mycard info.
       That is, their primary info: full name, primary email and primary phone.
    """
    #TODO Make those docs true, right now we return login email!
    details = dict()
    user_data = query_db(
        'select * from data where thing_id=%s',
        (user_id), one=False)
    for row in user_data:
        if row[2] == 'primary_phone' or row[2] == 'name' or row[2] == 'login_email':
            details[row[2]] = row[3]
    app.logger.debug('users mycard details: %s' % details)
    return details


def create_new_user(name, email, pw_hash):
    owner = 3
    cur = g.db.cursor()
    # First, create the user object in the things table
    cur.execute(
        'insert into things values (%s, %s, %s, %s, %s)',
        [None, owner, 'user', None, None])
    new_user_id = cur.lastrowid
    app.logger.debug('new thing created, id: %s' % new_user_id)
    # Next, add the users email address, name, and password hash to the data table
    cur.execute(
        'insert into data values (%s, %s, %s, %s)',
        [None, new_user_id, 'login_email', email])
    app.logger.debug('new data created, id: %s' % cur.lastrowid)
    cur.execute(
        'insert into data values (%s, %s, %s, %s)',
        [None, new_user_id, 'name', name])
    app.logger.debug('new data created, id: %s' % cur.lastrowid)
    cur.execute(
        'insert into data values (%s, %s, %s, %s)',
        [None, new_user_id, 'pw_hash', pw_hash])
    app.logger.debug('new data created, id: %s' % cur.lastrowid)
    g.db.commit()
    app.logger.debug('db-write: new user')
    return new_user_id



def validate_new_email(user_email):
    rv = query_db('select data_id from data where item=%s', user_email, one=True)
    app.logger.debug('validate_new_email -- email: %s, valid: %s' % (user_email, rv==None))
    return None if rv else user_email


def validate_new_name(user_name):
    rv = query_db('select data_id from data where item=%s', user_name, one=True)
    app.logger.debug('validate_new_name -- name: %s, valid: %s' % (user_name, rv==None))
    return None if rv else user_name


def validate_new_password(user_password):
    if len(user_password) < 8 or len(user_password) > 15:
        app.logger.debug('validate_new_password -- valid: %s' % 'NO')
        return None
    #TODO Add Regex
    app.logger.debug('validate_new_password -- valid: %s' % 'YES')
    return generate_password_hash(user_password)


@app.before_request
def before_request():
#TODO this has to be way to broad, is wasting db connections a bad idea or is this harmless?
    g.db = connect_db()
    g.user = None
    if 'user_id' in session:
        g.user = get_user_object(session['user_id'])


# Url routing / Views

@app.route('/')
def home():
    if g.user:
        return redirect(url_for('profile'))
    return render_template('welcome.html')


@app.route('/user')
@requires_login
def profile():
    user_id = g.user['user_id']
    if not mycard_initialized(user_id):
        app.logger.debug('user mycard_initialized is false, redirect to firstcard')
        return redirect(url_for('my_newcard'))
    return render_template('mycard.html', user_details=get_mycard_details(user_id=user_id))


@app.route('/newuser', methods=['GET', 'POST'])
@requires_login
def my_newcard():
    user_id = g.user['user_id']
    if mycard_initialized(user_id):
        app.logger.debug('newuser rerouting to user, reason: mycard init complete')
        return redirect(url_for('profile'))
    elif request.method == 'POST':
        user_phone = request.form['inputPhone']
        cur = g.db.cursor()
        cur.execute(
            'insert into data values (%s, %s, %s, %s)',
            [None, user_id, 'primary_phone', user_phone])
        app.logger.debug('new user phone added')
        cur.execute(
             'insert into data values (%s, %s, %s, %s)',
            [None, user_id, 'mycard_initialized', 1])
        app.logger.debug('mycard_initialized added')
        g.db.commit()
        app.logger.debug('db write -- primary_phone and mycard_initialized')
        return redirect(url_for('profile'))
    email_rv = query_db(
        'select item from data where thing_id=%s and item_title=%s',
        (g.user['user_id'], 'login_email'))
    current_email = email_rv[0] if email_rv is not None else None
    return render_template('myfirstcard.html', current_email=current_email)


@app.route('/register', methods=['GET', 'POST'])
def register():
    errors = None
    if request.method == 'POST':
        if RE_EMAIL.match(request.form['inputEmail']) is None:
            errors = 'Please enter a valid email address'
        elif RE_PWORD.match(request.form['inputPassword']) is None:
            errors = 'Please enter a valid password'
        else:
            new_user_email = validate_new_email(request.form['inputEmail'])
            new_user_name = validate_new_name(request.form['inputName'])
            new_user_password = validate_new_password(request.form['inputPassword'])
            app.logger.debug('rvs -- email: %s, name: %s, pw: %s' % (new_user_email, new_user_name, new_user_password))
            if new_user_email is None:
                errors = 'An account already exists for that Email Address, Please sign in instead.'
            elif new_user_name is None:
                errors = 'An account already exists for that Name, did you mean to sign in instead?'
            elif new_user_password is None:
                errors = 'That is an invalid password attempt, please try again. Note: passwords must be between 8 and 15 characters in length.'
            else:
                app.logger.debug('Attempting create new user')
                new_user_id = create_new_user(email=new_user_email, name=new_user_name, pw_hash=new_user_password)
                if new_user_id is not None:
                    session['user_id'] = new_user_id
                    flash('new user successfully added')
                    app.logger.debug('New user created')
                    return redirect(url_for('my_newcard'))
                else:
                    app.logger.debug('Failed to create new user. no lastrowid returned')
    return render_template('register.html', errors=errors)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if g.user:
        return redirect(url_for('home'))
    if request.method == 'POST':
        user_id = query_db(
            'select thing_id from data where item_title=%s and item=%s',
            ('login_email', request.form['inputEmail'].lower()), one=True)
        if user_id is None:
            flash('No account found for that email address. Please check your entry and try again.')
            return render_template('login.html')
        user_id = user_id[0]
        app.logger.info('%s -- %s: %s' % ('login', 'thing_id(user)', user_id))
        pw_hash = query_db(
            'select item from data where thing_id=%s and item_title=%s',
            [user_id, 'pw_hash'], one=True)
        if pw_hash is None:
            app.logger.error('%s -- %s: %s' % ('login', 'not found', 'item_title pw_hash'))
            flash("we're sorry, an error has occured. Please try again.")
            return render_template('login.html', emailtext=request.form['inputEmail'])
        pw_hash = pw_hash[0]
        pw_attempt = request.form['inputPassword']
        if not check_password_hash(pw_hash, pw_attempt):
            flash('Invalid password')
            return render_template('login.html', emailtext=request.form['inputEmail'])
        else:
            session['user_id'] = user_id
            flash('You have successfully logged in.')
            return redirect(url_for('profile'))
    return render_template('login.html')


@app.route('/logout')
def logout():
    """If there is a user currently logged in, logs them out."""
    session.pop('user_id', None)
    flash('You were logged out')
    return redirect(url_for('home'))


@app.route('/update', methods=['GET', 'POST'])
def update_profile():
    app.logger.debug('IMPORTANT! Not yet implemented: Update profile.')
    flash('Sorry, that in still under development!')
    return redirect(url_for('profile'))


@app.route('/contacts')
def view_contacts():
    flash("We're sorry, but that page is still under construction.")
    return redirect(url_for('home'))


@app.route('/add-contact')
def addnew():
    flash("We're sorry, but that page is still under construction.")
    return redirect(url_for('home'))


@app.route('/contact')
def view_contact():
    flash("We're sorry, but that page is still under construction.")
    return redirect(url_for('home'))


# If run as module, start dev server
if __name__ == '__main__':
    app.run()
