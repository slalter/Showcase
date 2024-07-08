import os
from google.cloud import secretmanager
is_testing = os.environ.get('TESTING', False)


client = secretmanager.SecretManagerServiceClient()
def load_secrets():
    os.environ['SECRET_KEY'] = client.access_secret_version(request={'name':'projects/322535312541/secrets/SECRET_KEY/versions/latest'}).payload.data.decode('UTF-8')
    os.environ['GOOGLE_CLIENT_ID'] = client.access_secret_version(request={'name':'projects/322535312541/secrets/GOOGLE_CLIENT_ID/versions/latest'}).payload.data.decode('UTF-8')
    os.environ['GOOGLE_CLIENT_SECRET'] = client.access_secret_version(request={'name':'projects/322535312541/secrets/GOOGLE_CLIENT_SECRET/versions/latest'}).payload.data.decode('UTF-8')

    os.environ['STRIPE_PUBLIC_KEY'] = client.access_secret_version(request={'name':'projects/322535312541/secrets/STRIPE_PUBLIC_KEY/versions/latest'}).payload.data.decode('UTF-8')
    os.environ['STRIPE_SECRET_KEY'] = client.access_secret_version(request={'name':'projects/322535312541/secrets/STRIPE_SECRET_KEY/versions/latest'}).payload.data.decode('UTF-8')

    os.environ['STRIPE_PUBLIC_KEY_TESTING'] = client.access_secret_version(request={'name':'projects/322535312541/secrets/STRIPE_PUBLIC_KEY_TESTING/versions/latest'}).payload.data.decode('UTF-8')
    os.environ['STRIPE_SECRET_KEY_TESTING'] = client.access_secret_version(request={'name':'projects/322535312541/secrets/STRIPE_SECRET_KEY_TESTING/versions/latest'}).payload.data.decode('UTF-8')

    os.environ['SENDGRID_API_KEY'] = client.access_secret_version(request={'name':'projects/322535312541/secrets/SENDGRID_API_KEY/versions/latest'}).payload.data.decode('UTF-8')
    os.environ['DRIVE_APPLICATION_CREDENTIALS'] = client.access_secret_version(request={'name':'projects/322535312541/secrets/DRIVE_APPLICATION_CREDENTIALS/versions/latest'}).payload.data.decode('UTF-8')

    os.environ['DRIVE_PROJECT_PATH'] = client.access_secret_version(request={'name':'projects/322535312541/secrets/DRIVE_PROJECT_PATH/versions/latest'}).payload.data.decode('UTF-8')
    os.environ['DRIVE_PROJECT_PATH_TESTING'] = client.access_secret_version(request={'name':'projects/322535312541/secrets/DRIVE_PROJECT_PATH_TESTING/versions/latest'}).payload.data.decode('UTF-8')

    os.environ['DRIVE_PROPOSAL_PATH'] = client.access_secret_version(request={'name':'projects/322535312541/secrets/DRIVE_PROPOSAL_PATH/versions/latest'}).payload.data.decode('UTF-8')
    os.environ['DRIVE_PROPOSAL_PATH_TESTING'] = client.access_secret_version(request={'name':'projects/322535312541/secrets/DRIVE_PROPOSAL_PATH_TESTING/versions/latest'}).payload.data.decode('UTF-8')