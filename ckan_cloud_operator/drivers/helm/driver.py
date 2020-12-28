import subprocess

from ckan_cloud_operator import kubectl
from ckan_cloud_operator import logs


def init(tiller_namespace_name):
    if kubectl.get('ns', tiller_namespace_name, required=False):
        logs.info('namespace already exists')
    else:
        subprocess.check_call(['kubectl', 'create', 'namespace', tiller_namespace_name])
    tiller_service_account = {
        "apiVersion": "v1",
        "kind": "ServiceAccount",
        "metadata": {
            "name": f"{tiller_namespace_name}-tiller",
            "namespace": tiller_namespace_name
        }
    }
    cluster_role_binding = {
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "kind": "ClusterRoleBinding",
        "metadata": {
          "name": f"{tiller_namespace_name}-tiller"
        },
        "roleRef": {
          "apiGroup": "rbac.authorization.k8s.io",
          "kind": "ClusterRole",
          "name": "cluster-admin"
        },
        "subjects": [
            {
                "kind": "ServiceAccount",
                "name": f"{tiller_namespace_name}-tiller",
                "namespace": tiller_namespace_name
            }
        ]
    }
    kubectl.apply(tiller_service_account)
    kubectl.apply(cluster_role_binding)
    subprocess.check_call(
        f'{}'.format("helm init --upgrade --service-account {tiller_namespace_name}-tiller --tiller-namespace {tiller_namespace_name} --history-max 10 --override spec.selector.matchLabels.'name'='tiller',spec.selector.matchLabels.'app'='helm' --output yaml | sed 's@apiVersion: extensions/v1beta1@apiVersion: apps/v1@' | kubectl apply -f -"),
        shell=True
    )


def deploy(tiller_namespace, chart_repo, chart_name, chart_version, release_name, values_filename=None, namespace=None,
           dry_run=False, chart_repo_name=None, values=None, service_account=None):
    if not chart_repo_name:
        chart_repo_name = 'ckan-cloud'
        logs.info(chart_repo_name=chart_repo_name)
    if chart_repo:
        subprocess.check_call(f'helm repo add "{chart_repo_name}" "{chart_repo}"', shell=True)
    assert not (values_filename and values), 'Only one of `values_filename` or `values` should be passed'

    version_args = f'--version "{chart_version}"' if chart_version else ''
    dry_run_args = '--dry-run --debug'
    cmd = f'helm --tiller-namespace {tiller_namespace} upgrade {release_name} {chart_name} ' \
          f' --install --namespace "{namespace}" -i {version_args}'
    if values_filename:
        cmd += f' -f {values_filename}'
    elif values:
        for key, value in values.items():
            cmd += f' --set {key}={value}'
    logs.info('Running helm upgrade --dry-run')
    if logs.CKAN_CLOUD_OPERATOR_DEBUG_FILE:
        logs.info(f'helm dry run debug output is written to debug log file: {logs.CKAN_CLOUD_OPERATOR_DEBUG_FILE}')
        with open(logs.CKAN_CLOUD_OPERATOR_DEBUG_FILE, 'a') as f:
            subprocess.check_call(f'{cmd} {dry_run_args}', shell=True, stdout=f, stderr=subprocess.STDOUT)
    else:
        subprocess.check_call(f'{cmd} {dry_run_args}', shell=True)
    if not dry_run:
        logs.info('Running helm upgrade for real this time')
        subprocess.check_call(cmd, shell=True)


def delete(tiller_namespace, release_name):
    subprocess.check_call(f'helm --tiller-namespace {tiller_namespace} delete --purge --timeout 5 {release_name}', shell=True)
