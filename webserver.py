import random
import string
from datetime import datetime, timedelta

import flask
import keycloak
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_pyoidc import OIDCAuthentication
from flask_pyoidc.provider_configuration import ProviderConfiguration, ClientMetadata
from flask_pyoidc.user_session import UserSession

import config_reader
import token_database
from keycloak import KeycloakAdmin

app = Flask(__name__)
app.config.update(
    OIDC_REDIRECT_URI='https://invite.ellri.ch',
    SECRET_KEY='lee6mahl9oop9AhL5thaephaiJohjoh8eexaibeil9yu4faiveiped9shi2FaeTe'
)

config = config_reader.load_config('settings.yml')
# Set up the Keycloak admin client
keycloak_admin = KeycloakAdmin(
    server_url=config['server_url'],
    realm_name=config['realm_name'],
    client_id=config['client_id'],
    client_secret_key=config['client_secret_key']
)

client_metadata = ClientMetadata(client_id=config['client_id'], client_secret=config['client_secret_key'],
                                 scope=['openid', 'profile'])
provider_config = ProviderConfiguration(issuer='https://auth.ellri.ch/realms/master/',
                                        client_metadata=client_metadata)

auth = OIDCAuthentication({'default': provider_config}, app)


@app.route('/api')
@auth.oidc_auth('default')
def index():
    user_session = UserSession(flask.session)
    return jsonify(
        access_token=user_session.access_token,
        id_token=user_session.id_token,
        userinfo=user_session.userinfo
    )


@app.route('/admin')
@auth.oidc_auth('default')
def admin():
    user_session = UserSession(flask.session)

    if not is_authorized(user_session):
        return 'User not authorized. Access denied.'

    # Retrieve all tokens from the 'invite_tokens' table
    all_tokens = token_db.select_all_tokens()
    # for t in all_tokens:
    #     print(f'Token: {t.id}, {t.token_value}, {t.uses_left}, {t.valid_until}, {t.assigned_group}, {t.assigned_group_id}')

    # Get groups from keycloak
    keycloak_groups = keycloak_admin.get_groups()

    return render_template('admin.html', has_desired_role=is_authorized(user_session), all_tokens=all_tokens,
                           groups=keycloak_groups)


def is_authorized(user_session, desired_role='invite-admin'):
    user_roles = user_session.id_token.get('resource_access', {}).get('invite-backend', {}).get('roles', [])
    # Check if the user has a specific role
    return desired_role in user_roles


@app.route('/admin/add_token', methods=['POST'])
@auth.oidc_auth('default')
def add_token():
    user_session = UserSession(flask.session)

    if not is_authorized(user_session):
        return 'User not authorized. Access denied.'

    if request.method == 'POST':
        try:
            # Get the expiration days from the form
            expiration_days = int(request.form['expiration_days'])
            uses = int(request.form['uses'])
            assigned_group_id = str(request.form['assigned_group'])

            # Ensure the provided value is valid
            if expiration_days <= 0:
                flash('Invalid expiration days value. Please enter a positive number.', 'error')
                return redirect(url_for('admin'))

            new_token = generate_token()

            # Calculate the expiration time based on the provided days
            expiration_time = datetime.now() + timedelta(days=expiration_days)
            expiration_str = expiration_time.strftime('%Y-%m-%d %H:%M:%S')

            assigned_group_name = keycloak_admin.get_group(assigned_group_id).get('name')

            # Insert the new token into the 'invite_tokens' table with the calculated expiration time

            token_db.insert_token(new_token, expiration_str, uses, assigned_group_name, assigned_group_id)

            flash(f'New token added: {new_token}', 'success')
        except ValueError:
            flash('Invalid expiration days value. Please enter a valid number.', 'error')

    return redirect(url_for('admin'))


@app.route('/admin/delete_token', methods=['POST'])
@auth.oidc_auth('default')
def delete_token():
    user_session = UserSession(flask.session)

    if not is_authorized(user_session):
        return render_template('message.html',
                               message='User not authorized. Access denied!')

    if request.method == 'POST':
        token_value = request.form.get('delete_token')

        # Delete the specified token
        token_db.remove_token(token_value)

        flash(f'Token deleted: {token_value}', 'success')

    return redirect(url_for('admin'))


def generate_token(length=16):
    """Generate a random token."""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))


@app.route('/register', methods=['GET', 'POST'])
def register():
    token = request.args.get('invite_token')
    if is_valid_token(token):
        if request.method == 'POST':
            # Handle user registration form submission
            username = request.form['username']
            email = request.form['email']
            first_name = request.form['first_name']
            last_name = request.form['last_name']

            # Process the submitted data (you can save it to a database, for example)
            # For now, let's just print the values
            print(
                f"Received registration: Invite_Token - {token}, Username - {username}, Email - {email}, First Name - {first_name}, Last Name - {last_name}")
            # Define user attributes
            new_user_attributes = {
                "username": username,
                "email": email,
                "enabled": True,
                "firstName": first_name,
                "lastName": last_name,
            }
            # Create the new user
            try:
                created_user = keycloak_admin.create_user(new_user_attributes, exist_ok=True)
                if created_user:
                    keycloak_admin.group_user_add(created_user, token_db.select_token(token).assigned_group_id)
                    keycloak_admin.send_update_account(user_id=created_user,
                                                       payload=['UPDATE_PASSWORD', 'VERIFY_EMAIL'])  # 'CONFIGURE_TOTP'
                    token_db.update_token_uses(token)
                    # Print the created user details
                    print("User created successfully:")
                    print(created_user)

                    return render_template('message.html',
                                           message='Successfully registered! You will receive a setup mail soon.')
            except keycloak.exceptions.KeycloakPostError:
                print('User could not be created!')
                return render_template('message.html',
                                       message='User could not be created. Plase try again or contact your administrator!')

        return render_template('register.html')

    else:
        return render_template('message.html',
                               message='Invalid or expired invitation token. Access denied!')


def is_valid_token(token):
    # Check if the token exists in the 'invite_tokens' table
    token = token_db.select_token(token)

    if token:
        # Check if the token is not expired
        expiration_time = datetime.strptime(token.valid_until, '%Y-%m-%d %H:%M:%S')
        current_time = datetime.now()
        if expiration_time > current_time and token.uses_left > 0:
            return True

    return False


if __name__ == '__main__':
    token_db = token_database.DatabaseAdapter("token.db")
    app.run(host='100.84.250.120', debug=True)
