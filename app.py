from __future__ import absolute_import
import MySQLdb
from flask import Flask, render_template, request, redirect, url_for, session, g, flash
from werkzeug import check_password_hash, generate_password_hash
from decorators import requires_login
import logging


app = Flask(__name__)
app.config.from_object('config')


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
    """Returns a tuple representing the user.
       The tuple is of length 2 and in the form(users thing_id, user full name).
       Was created for ease of display and passing to templates/cookies.
    """
# This sucks. Whats the point if we are just taking in user_id?
# Also, if this is the mthod being called by before_request, 
# then this is the ohly method verifying thyat the given user_id
# is valid. Seems like something that certainly needs more
# attention and security.
    name = query_db(
        'select item from data where thing_id=%s and item_title=%s',
        (user_id, 'name'),
        one=True)
    if name is not None:
        name = ' '.join([x.capitalize() for x in name[0].split()])
    return (user_id, name)


@app.before_request
def before_request():
    g.user = None
    if 'user_id' in session:
        app.logger.debug('%s -- %s: %s' % ('before_request', 'user_id', session['user_id']))
        g.user = get_user_object(session['user_id'])
        app.logger.debug('%s -- %s: %s' % ('before_request', 'g.user', g.user))
    else:
        app.logger.debug('%s -- %s: %s' % ('before_request', 'user_id', 'None'))


# Url routing / Views
@app.route('/')
@requires_login
def home():
    return render_template('view.html')


@app.route('/user')
@requires_login
def profile():
    return render_template('mycard.html')


@app.route('/add-contact')
@requires_login
def addnew():
    return render_template('add.html') 


@app.route('/contact')
@requires_login
def view_contact():
    return render_template('contact-profile.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if g.user:
        app.logger.debug('%s -- %s: %s' % ('login', 'user present', g.user))
        return redirect(url_for('home'))
    app.logger.debug('%s -- Method: %s' % ('login', request.method))
    if request.method == 'POST':
        app.logger.debug('%s -- %s: %s' % ('login', 'inputEmail', request.form['inputEmail'].lower()))
        user_id = query_db(
            'select thing_id from data where item_title=%s and item=%s',
            ('login_email', request.form['inputEmail'].lower()), one=True)

        if user_id is None:
            flash('No account found for that email address. Please check your entry and try again.')
            app.logger.debug('%s -- %s: %s' % ('login', 'not found', request.form['inputEmail']))
            return render_template('login.html')
        user_id = user_id[0]
        app.logger.debug('%s -- %s: %s' % ('login', 'thing_id(user)', user_id))
        pw_hash = query_db(
            'select item from data where thing_id=%s and item_title=%s',
            [user_id, 'pw_hash'], one=True)

        if pw_hash is None:
            app.logger.error('%s -- %s: %s' % ('login', 'not found', 'item_title pw_hash'))
            flash("we're sorry, an error has occured. Please try again.")
            return render_template('login.html', emailtext=request.form['inputEmail'])
        pw_hash = pw_hash[0]
        pw_attempt = request.form['inputPassword']
        app.logger.debug('%s -- %s: %s' % ('login', 'inputPassword', pw_attempt))
        if not check_password_hash(pw_hash, pw_attempt):
            flash('Invalid password')
            return render_template('login.html', emailtext=request.form['inputEmail'])
        else:
            session['user_id'] = user_id
            app.logger.debug('%s -- %s: %s' % ('login', 'user_id stored in session', user_id))
            flash('You have successfully logged in.')
            return redirect(url_for('home'))
    return render_template('login.html')


@app.route('/logout')
def logout():
    """If there is a user currently logged in, logs them out."""
    session.pop('user_id', None)
    app.logger.debug('%s -- %s: %s' % ('logout', 'user_id in session', session['user_id'] if 'user_id' in session else 'None'))
    flash('You were logged out')
    return redirect(url_for('home'))


# Run on local network
if __name__ == '__main__':
    app.run()
