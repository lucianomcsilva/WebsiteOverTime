import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///birthdays.db")

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":

        # TODO: Add the user's entry into the database
        # Check if ID comes in the form. If doesn`t, it is a insert
        id = request.form.get('id', type=int)
        if not id:
            name = request.form.get('name').strip()
            month = request.form.get('month', type=int)
            day = request.form.get('day', type=int)
            if not name or not month or not day:
                flash("You must provide information to insert")
                return redirect("/")
            elif month > 12:
                flash("Invalid Month")
                return redirect("/")
            elif  (month in [1,3,5,7,8,10,12] and day > 31) or (month in [4,6,9,11] and day > 30) or (month == 2 and day > 29):
                flash("Invalid Day")
                return redirect("/")

            db.execute("INSERT INTO birthdays (name, month, day) VALUES (?,?,?)", name, month, day)
            flash(f"Inserted {name}'s birthday at {month}/{day}")
            return redirect("/")
        else:
            #must be the delete
            person = db.execute("SELECT * FROM birthdays WHERE id = ?", id)
            name = person[0]['name']
            month = person[0]['month']
            day = person[0]['day']
            db.execute("DELETE FROM birthdays WHERE id = ?", id)
            flash(f"Deleted {name}'s birthday at {month}/{day}")
            return redirect("/")

    else:

        # TODO: Display the entries in the database on index.html
        birthdays = db.execute('SELECT * FROM birthdays')
        return render_template("index.html", birthdays=birthdays)


if __name__ == '__main__':
      app.run(host='0.0.0.0', port=5000, static_url_path='', static_folder='./screenshots/')