#!/usr/bin/env bash
# Operator-authorized GitHub push and HTTPS deployment on the existing VM.
# Does not activate trading, change broker keys or restart the trading process.
set -euo pipefail
DASH_ROOT=$(cd "$(dirname "$0")/.." && pwd -P)
cd "$DASH_ROOT"
[[ -z $(git status --porcelain) ]] || { echo 'Commit or preserve local changes before deployment.' >&2; exit 2; }
[[ $(git branch --show-current) = main ]] || { echo 'Deploy the reviewed main branch.' >&2; exit 2; }
DASH_SHA=$(git rev-parse HEAD)
DASH_PROJECT=project-cead8bae-10ea-4ea9-875
DASH_ZONE=asia-south1-a
DASH_VM=sablestone-dhan-cas
DASH_HOST=dhan.34.100.255.111.sslip.io
DASH_TAG=dhan-private-dashboard
DASH_RULE=dhan-private-dashboard-https
DASH_TEMP=$(mktemp -d)
trap 'rm -rf "$DASH_TEMP"' EXIT
python3 -m pytest tests/test_dashboard.py
node --check dhan_cas_bot/dashboard/static/app.js
# Prove account/project reachability before publishing.
gcloud compute instances describe "$DASH_VM" --project="$DASH_PROJECT" --zone="$DASH_ZONE" --format=json > "$DASH_TEMP/vm.json"
python3 - "$DASH_TEMP/vm.json" <<'PY'
import json,sys
v=json.load(open(sys.argv[1]))
assert v['status']=='RUNNING', 'Existing VM is not running'
assert v['networkInterfaces'][0]['accessConfigs'][0]['natIP']=='34.100.255.111', 'Unexpected VM public IP'
PY
DASH_NETWORK=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["networkInterfaces"][0]["network"].rsplit("/",1)[-1])' "$DASH_TEMP/vm.json")
git push origin main
[[ $(git ls-remote origin refs/heads/main | cut -f1) = "$DASH_SHA" ]] || { echo 'Remote commit mismatch.' >&2; exit 2; }
git bundle create "$DASH_TEMP/source.bundle" main
DASH_STAGE=$(gcloud compute ssh "$DASH_VM" --project="$DASH_PROJECT" --zone="$DASH_ZONE" --tunnel-through-iap --command='mktemp -d /tmp/dhan-dashboard.XXXXXXXX')
[[ $DASH_STAGE =~ ^/tmp/dhan-dashboard\.[A-Za-z0-9]{8}$ ]] || { echo 'Unexpected remote staging directory.' >&2; exit 2; }
gcloud compute scp "$DASH_TEMP/source.bundle" "$DASH_VM:$DASH_STAGE/source.bundle" --project="$DASH_PROJECT" --zone="$DASH_ZONE" --tunnel-through-iap
# Public HTTPS only; the WSGI server never binds a public interface.
gcloud compute firewall-rules list --project="$DASH_PROJECT" --filter="name=$DASH_RULE" --format=json > "$DASH_TEMP/firewall.json"
python3 - "$DASH_TEMP/firewall.json" "$DASH_NETWORK" <<'PY'
import json,sys
rules=json.load(open(sys.argv[1]))
if rules:
    r=rules[0]
    assert r['network'].rsplit('/',1)[-1]==sys.argv[2]
    assert r.get('direction')=='INGRESS' and not r.get('disabled',False)
    assert r.get('targetTags')==['dhan-private-dashboard']
    assert r.get('sourceRanges')==['0.0.0.0/0']
    assert r.get('allowed')==[{'IPProtocol':'tcp','ports':['80','443']}], 'Existing firewall rule differs; not replacing it'
PY
if [[ $(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1]))))' "$DASH_TEMP/firewall.json") = 0 ]]; then
  gcloud compute firewall-rules create "$DASH_RULE" --project="$DASH_PROJECT" --network="$DASH_NETWORK" --direction=INGRESS --action=ALLOW --rules=tcp:80,tcp:443 --source-ranges=0.0.0.0/0 --target-tags="$DASH_TAG"
fi
gcloud compute instances add-tags "$DASH_VM" --project="$DASH_PROJECT" --zone="$DASH_ZONE" --tags="$DASH_TAG"
gcloud compute ssh "$DASH_VM" --project="$DASH_PROJECT" --zone="$DASH_ZONE" --tunnel-through-iap --command="set -eu; git clone '$DASH_STAGE/source.bundle' '$DASH_STAGE/source'; git -C '$DASH_STAGE/source' checkout --detach '$DASH_SHA'; sudo bash '$DASH_STAGE/source/ops/install_dashboard.sh' '$DASH_SHA' '$DASH_HOST'"
# Verify the certificate and mandatory authentication from outside the VM.
DASH_HTTP=$(curl --silent --show-error --retry 12 --retry-delay 5 --retry-all-errors --max-time 15 -o "$DASH_TEMP/response" -w '%{http_code}' "https://$DASH_HOST/")
[[ $DASH_HTTP = 401 ]] || { echo "Unexpected HTTPS status: $DASH_HTTP" >&2; exit 1; }
echo "Verified public HTTPS authentication at https://$DASH_HOST/ (commit $DASH_SHA)."
echo 'Sign in with the private login file on the VM, then verify that observations are current.'
