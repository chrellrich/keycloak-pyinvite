import yaml


def load_config(config_file_path='settings.yml', default_config="""
# Keycloak config
server_url: "https://auth.example.com"
realm_name: "master"
client_id: "cliend-id"
client_secret_key: "client-secret"
"""):
    try:
        with open(config_file_path) as config_file:
            return yaml.safe_load(config_file)
    except FileNotFoundError:
        print(f"Config file not found. Creating a default configuration file at {config_file_path}")
        create_default_config(config_file_path, default_config)
        return load_config()
    except yaml.YAMLError as e:
        print(f"Error in the configuration file: {e}")
        exit(1)


def create_default_config(config_file_path, default_config="default: True"):
    with open(config_file_path, 'w') as default_config_file:
        default_config_file.write(default_config)
