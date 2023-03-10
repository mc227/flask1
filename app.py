"""
Dereck Watters Flask App 2.0
"""
import getpass
import json
import json
import os
from datetime import datetime

from cryptography.fernet import Fernet
from flask import Flask, redirect, url_for, render_template, request, session, flash
from ip2geotools.databases.noncommercial import DbIpCity

app = Flask(__name__)
app.secret_key = os.urandom(16)

PATH = f"{os.getcwd()}/static/data/data.json"

def get_date():
    """
    This function gets the current date (e.g. April 24, 2020).
    :return: date
    """
    today = datetime.today()
    date = today.strftime("%B %d, %Y")  # Month, day and year

    return date



@app.route("/", methods=["GET", "POST"])
def login():
    """
    Checks for valid email/password combo.
    :return: Login page
    """
    if request.method == "POST":
        session.pop("user_id", None)

        email = request.form["email"]
        password = request.form["password"]

        if check_user(email, password):
            return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/password-reset", methods=["GET", "POST"])
def reset():
    """
    Attempts to reset account password after performing check.
    :return: Password Reset page
    """
    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        if check_user_exists(email):
            if check_password(password):
                if change_password(email, password):
                    session.pop('_flashes', None)
                    flash("Password changed successfully.", category="success")
                    return redirect(url_for("login"))
            else:
                flash("Your password does not meet the criteria. Please try again.", category="warning")
        else:
            flash("User does not exist.", category="danger")

    return render_template("password-reset.html")

@app.route("/index")
def index():
    """
    renders index .html
    """
    date = get_date()

    return render_template("index.html", content=[date])

@app.route("/register", methods=["GET", "POST"])
def register():
    """
    Registers a new user account.
    :return: Registration page
    """
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        if check_user_exists(email):
            flash("User already exists.", category="warning")
        elif check_password(password):
            if create_account(email, password):
                flash("Your account has been created successfully. Please login to continue.",
                      category="success")
                return redirect(url_for("login"))
        else:
            flash("Your password does not meet the criteria. Please try again.", category="warning")

    return render_template("register.html")



@app.route("/about")
def about():
    """
    renders the about page
    """
    return render_template("about.html")


@app.route("/contact")
def contact():
    """
    renders contact page
    """
    return render_template("contact.html")

@app.route("/admin")
def admin():
    """
    Redirects to Login page
    :return: Login page
    """
    return redirect((url_for("login")))


def check_user(email, password):
    """
    Checks if user exists and logs failed login attempt if password is incorrect.
    :param email:
    :param password:
    :return: Boolean state for user check
    """
    ip_addr = request.environ['REMOTE_ADDR']

    try:
        with open(PATH, "r", encoding="utf-8") as in_file:
            data = json.load(in_file)

        user_exists = False
        for user in data["USERS"]:
            for key in user.keys():
                if key == email:
                    user_exists = True
                    if handle_password(user[email]["KEY"],
                                       user[email]["PASSWORD"], decrypt=True) == password:
                        if not check_logs(ip_addr):
                            session["user_id"] = user[email]["USERNAME"]
                            return True
                    else:
                        check_logs(ip_addr)
                        flash("Your password is incorrect.", category="danger")
                        return False

        if not user_exists:
            flash("User does not exist.", category="warning")

    except (KeyError, IOError):
        flash("Cannot communicate with server. Please try again later.", category="danger")
        return False

def check_user_exists(email):
    """
    Checks if user exists.
    :param email:
    :return: Boolean state for user check
    """
    try:
        with open(PATH, "r", encoding="utf-8") as in_file:
            data = json.load(in_file)

        user_exists = False
        for user in data["USERS"]:
            if email in user:
                user_exists = True
                break

        return user_exists

    except (KeyError, IOError):
        flash("Cannot communicate with server. Please try again later.", category="danger")
        return False


def handle_password(key, password, decrypt=False):
    """
    Uses generated cipher key to encrypt/decrypt password.
    :param key:
    :param password:
    :param decrypt:
    :return: password in desired format
    """
    if decrypt:
        key = str.encode(key)
        cipher_suite = Fernet(key)
        user_password = str.encode(password)
        ciphered_text = cipher_suite.decrypt(user_password)
        deciphered_text = bytes.decode(ciphered_text)

        return deciphered_text
    else:
        key = Fernet.generate_key()
        new_password = str.encode(password)
        cipher_suite = Fernet(key)
        ciphered_text = cipher_suite.encrypt(new_password)  # Required to be bytes
        new_password = bytes.decode(ciphered_text)
        cipher_key = bytes.decode(key)

        return cipher_key, new_password

def check_password(password):
    """
    Checks password against NIST SP 800-63B criteria and flashes
    warning to user if password criteria is not met.
    :param password:
    :return: Boolean state for password check
    """
    common_passwords = []

    try:
        with open(PATH, "r", encoding="utf-8") as in_file:
            data = json.load(in_file)

        common_passwords = data["COMMON PASSWORDS"]
    except (KeyError, IOError):
        pass

    if 8 < len(password) > 64:
        flash("Your password must be greater than 7 characters and less than 65.",
              category="warning")
        return False
    elif password in common_passwords:
        flash("Your password is too common, please try something more complicated.",
              category="warning")
        return False

    return True



def check_logs(ip_addr):
    """
    Checks logs for login attempts. Locks account if user has more than
    (5) failed login attempts within (5) minutes and flags account with
    geolocation if successful coordinates are obtained.
    :param ip_addr:
    :return: Boolean acc_locked
    """
    date, time = datetime.now().strftime('%Y-%m-%d %H:%M:%S').split()
    acc_locked = False
    ip_found = False

    try:
        with open(PATH, "r") as in_file:
            data = json.load(in_file)

        for log in data["LOGS"]:
            for ip_var in log.keys():
                if ip_var == ip_addr:
                    ip_found = True
                    if int(time.replace(":", "")) - int(log[ip_var]["TIME"].replace(":", "")) > 300:
                        acc_locked = False
                        log[ip_var].update(ATTEMPT=1, DATE=date, TIME=time, FLAGS="")
                    else:
                        log[ip_var]["ATTEMPT"] += 1
                        log[ip_var].update(DATE=date, TIME=time)
                        if log[ip_var]["ATTEMPT"] > 5:
                            acc_locked = True
                            flash("Too many login attempts. Please wait 5 minutes and try again.",
                                  category="warning")
                            flag = DbIpCity.get('147.229.2.90', api_key='free')
                            flag = flag if flag else "(Unable to obtain location)"
                            log[ip_var].update(FLAGS=f"{ip_addr} had {log[ip_var]['ATTEMPT']} \
                                           failed login attempts within 5 "
                                                 f"minutes on {date} from LAT/LONG: \
                                                    {flag.latitude, flag.longitude}.")

        if not ip_found:
            data["LOGS"].append({ip_addr: {"ATTEMPT": 1, "DATE": date, "TIME": time, "FLAGS": ""}})

        with open(PATH, "w", encoding="utf-8") as out_file:
            json.dump(data, out_file, indent=4, sort_keys=True)
    except (KeyError, IOError):
        pass

    return acc_locked


def create_account(email, password):
    """
    Creates a new user account.
    :param email:
    :param password:
    """
    try:
        with open(PATH, "r", encoding="utf-8") as in_file:
            data = json.load(in_file)
    except (IOError, ValueError):
        data = {"USERS": []}

    for user in data["USERS"]:
        if email in user:
            flash("User already exists.", category="warning")
            return False

    key = Fernet.generate_key()
    cipher_suite = Fernet(key)
    ciphered_text = cipher_suite.encrypt(str.encode(password))
    user_data = {
        email: {
            "KEY": bytes.decode(key),
            "PASSWORD": bytes.decode(ciphered_text),
            "USERNAME": email.split("@")[0],
            "REGISTERED": get_date()
        }
    }

    data["USERS"].append(user_data)

    with open(PATH, "w", encoding="utf-8") as out_file:
        json.dump(data, out_file)

    return True



def change_password(email, password):
    """
    Changes password after encrypting supplied password.
    :param email:
    :param password:
    :return: Boolean state for password change
    """
    try:
        with open(PATH, "r", encoding="utf-8") as in_file:
            data = json.load(in_file)

        for user in data["USERS"]:
            for key in user.keys():
                if key == email:
                    cipher_key, new_password = handle_password(None, password)
                    user[key].update(KEY=cipher_key, PASSWORD=new_password)

                    with open(PATH, "w", encoding="utf-8") as out_file:
                        json.dump(data, out_file, indent=4, sort_keys=True)
                    return True
        return False
    except (KeyError, IOError):
        flash("Unable to change password.", category="danger")


if __name__ == "__main__":
    app.run()
