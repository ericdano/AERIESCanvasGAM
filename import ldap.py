import ldap

def lambda_handler(event, context):
    """Creates a user in LDAP.

    Input event expects the following event structure:
    {
        "username": "username_to_create",
        "password": "user_password",
        "givenName": "user_given_name",
        "sn": "user_surname",
        "mail": "user_email",
        "ldap_uri": "ldap://ldap_server_uri",
        "base_dn": "base_distinguished_name",
        "bind_dn": "bind_distinguished_name",
        "bind_password": "bind_password"
    }
    """

    # Extract required parameters from the event
    username = event.get("username")
    password = event.get("password")
    givenName = event.get("givenName")
    sn = event.get("sn")
    mail = event.get("mail")
    ldap_uri = event.get("ldap_uri")
    base_dn = event.get("base_dn")
    bind_dn = event.get("bind_dn")
    bind_password = event.get("bind_password")

    # Validate required parameters
    if not all([username, password, givenName, sn, mail, ldap_uri, base_dn, bind_dn, bind_password]):
        raise ValueError("Missing required parameters in the event")

    try:
        # Connect to LDAP with TLS
        with ldap.initialize(ldap_uri, tls=True)) as connection:
            
            # Optionally specify the CA certificate file path if needed
            # connection.set_option(ldap.OPT_X_TLS_CACERTFILE, "path/to/ca_cert.pem")
            connection.simple_bind_s(bind_dn, bind_password)

            # Construct user DN
            user_dn = f"cn={username},{base_dn}"

            # Create user attributes
            attrs = [
                ("objectclass", ["top", "person", "organizationalPerson", "inetOrgPerson"]),
                ("cn", [username]),
                ("sn", [sn]),
                ("givenName", [givenName]),
                ("mail", [mail]),
                ("userPassword", [password]),
            ]

            # Add the user to LDAP
            connection.add_s(user_dn, attrs)

            return {"statusCode": 200, "message": f"User {username} created successfully"}

    except ldap.LDAPError as e:
        raise Exception(f"Error creating user: {e}")