#!/usr/bin/env python3

# FLASK with LDAP3 authentication against active directory and authorization check for group membership
# Written by Maximilian Thoma 2023
# Visit: https://lanbugs.de for more ...

from functools import wraps
from flask import Flask, request, redirect, url_for, render_template, abort
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from ldap3 import Server, Connection, SUBTREE, SIMPLE

# LDAP Settings
LDAP_USER = "CN=LDAP Bind,CN=Users,DC=ad,DC=local"
LDAP_PASS = "SuperSecret12345567"
LDAP_SERVER = "ldap://ad01.ad.local"
AD_DOMAIN = "ADLOCAL"
SEARCH_BASE = "CN=Users,DC=ad,DC=local"

# Init Flask
app = Flask(__name__)
app.secret_key = "ThisSecretIsVeryWeakDoItBetter"

# Init LoginManager
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)


class User(UserMixin):
    """
    The user model
    """
    def __init__(self, username):
        self.id = username
        self.groups = []


def authenticate_ldap(username, password):
    """
    Check authentication of user against AD with LDAP
    :param username: Username
    :param password: Password
    :return: True is authentication is successful, else False
    """
    server = Server(LDAP_SERVER, use_ssl=True)

    try:
        with Connection(server,
                        user=f'{AD_DOMAIN}\\{username}',
                        password=password,
                        authentication=SIMPLE,
                        check_names=True,
                        raise_exceptions=True) as conn:
            if conn.bind():
                print("Authentication successful")
                return True
    except Exception as e:
        print(f"LDAP authentication failed: {e}")
    return False


def get_user_groups(username):
    """
    Connect to LDAP and query for all groups
    :param username: Username
    :return: List of group names
    """
    server = Server(LDAP_SERVER, use_ssl=True)

    with Connection(server,
                    user=LDAP_USER,
                    password=LDAP_PASS,
                    auto_bind=True) as conn:
        search_filter = f'(sAMAccountName={username})'
        conn.search(search_base=SEARCH_BASE,
                    search_filter=search_filter,
                    attributes=['memberOf'],
                    search_scope=SUBTREE)

        if conn.entries:
            user_entry = conn.entries[0]
            group_dns = user_entry.memberOf

            group_names = [group.split(',')[0].split('=')[1] for group in group_dns]

            return group_names

    return []


@login_manager.user_loader
def load_user(user_id):
    """
    The user_loader of flask-login, this will load Usermodel and the groups from AD
    :param user_id: Username
    :return: user object
    """
    user = User(user_id)
    user.groups = get_user_groups(user_id)
    return user


def group_required(groups):
    """
    Decorator to check group membership
    :param groups: list of groups which are allowed to see the site
    """
    def decorator(func):
        @wraps(func)
        def decorated_function(*args, **kwargs):

            for g in groups:
                if current_user.is_authenticated and g in current_user.groups:
                    return func(*args, **kwargs)

            abort(403)
        return decorated_function
    return decorator


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Login page
    """
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if authenticate_ldap(username, password):
            user = User(username)
            login_user(user)
            return redirect(url_for('user_panel'))

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """
    Logout page
    """
    logout_user()
    return redirect(url_for('login'))


@app.route('/admin')
@login_required
@group_required(["p_admin"])
def admin_panel():
    """
    Protected admin panel, only users of group p_admin are allowed to see the page 
    """
    return 'Admin Panel'


@app.route('/user')
@login_required
@group_required(["p_user", "p_admin"])
def user_panel():
    """
    Protected user panel, only users of group p_user and p_admin are allowed to see the page 
    """
    return 'User Panel'


if __name__ == "__main__":
    app.run(debug=True)
