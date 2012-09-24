from flask import Flask, render_template

DEBUG = False 

app = Flask(__name__)
app.config.from_object(__name__)


# Url routing / Views
@app.route('/')
def home():
    return render_template('view.html')


@app.route('/user')
def profile():
    return render_template('mycard.html')


@app.route('/add-contact')
def addnew():
    return render_template('add.html') 


# Run on local network
if __name__ == '__main__':
    app.run()
