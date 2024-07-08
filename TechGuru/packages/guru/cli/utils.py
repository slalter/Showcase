import yaml


# Function to load settings from packages.guru_settings.yml
def load_settings():
    with open('guru_settings.yml', 'r') as f:
        settings = yaml.safe_load(f)
    return settings


guru_settings = load_settings()
