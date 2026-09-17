# dev environment values.
#
# Migrated 2026-06-07 from deepcab-dev → garassino-ml (region us-central1 → europe-west1).
# Operates in show-and-destroy mode: `make show` to provision, `make destroy` after demos.
# project_number must be the garassino-ml project number — fetch with:
#   gcloud projects describe garassino-ml --format='value(projectNumber)'

project_id     = "garassino-ml"
project_number = "920423386248"
region         = "europe-west1"

gh_owner         = "juan-garassino"
gh_api_repo      = "deepCab"
gh_platform_repo = "deepCab-platform"

# Real images live permanently on GHCR (public). Hello-world is the bootstrap
# placeholder Cloud Run needs to first stand up before the image-build workflow
# pushes the real container. `lifecycle.ignore_changes` keeps TF from reverting.
api_image     = "us-docker.pkg.dev/cloudrun/container/hello"
retrain_image = "us-docker.pkg.dev/cloudrun/container/hello"
# Production tags pushed by CI:
#   ghcr.io/juan-garassino/deepcab-api:<sha>
#   ghcr.io/juan-garassino/deepcab-retrain:<sha>

mlflow_tracking_uri = "http://mlflow.dev.deepcab.local:5000"
