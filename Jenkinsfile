/*
 * SPDX-License-Identifier: GPL-2.0+
*/

try { // massive try{} catch{} around the entire build for failure notifications

node('fedora') {
    checkout scm
    sh 'sudo dnf -y builddep greenwave.spec'
    sh 'sudo dnf -y install python2-flake8 pylint python2-sphinx python-sphinxcontrib-httpdomain'
    stage('Invoke Flake8') {
        sh 'flake8'
    }
    stage('Invoke Pylint') {
        sh 'pylint --reports=n greenwave'
    }
    stage('Build Docs') {
        sh 'make -C docs html'
        archiveArtifacts artifacts: 'docs/_build/html/**'
    }
    /* Can't use GIT_BRANCH because of this issue https://issues.jenkins-ci.org/browse/JENKINS-35230 */
    def git_branch = sh(returnStdout: true, script: 'git rev-parse --abbrev-ref HEAD').trim()
    if (git_branch == 'master') {
        stage('Publish Docs') {
            sshagent (credentials: ['pagure-greenwave-deploy-key']) {
                sh '''
                mkdir -p ~/.ssh/
                touch ~/.ssh/known_hosts
                ssh-keygen -R pagure.io
                echo 'pagure.io,140.211.169.204 ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC198DWs0SQ3DX0ptu+8Wq6wnZMrXUCufN+wdSCtlyhHUeQ3q5B4Hgto1n2FMj752vToCfNTn9mWO7l2rNTrKeBsELpubl2jECHu4LqxkRVihu5UEzejfjiWNDN2jdXbYFY27GW9zymD7Gq3u+T/Mkp4lIcQKRoJaLobBmcVxrLPEEJMKI4AJY31jgxMTnxi7KcR+U5udQrZ3dzCn2BqUdiN5dMgckr4yNPjhl3emJeVJ/uhAJrEsgjzqxAb60smMO5/1By+yF85Wih4TnFtF4LwYYuxgqiNv72Xy4D/MGxCqkO/nH5eRNfcJ+AJFE7727F7Tnbo4xmAjilvRria/+l' >>~/.ssh/known_hosts
                rm -rf docs-on-pagure
                git clone ssh://git@pagure.io/docs/greenwave.git docs-on-pagure
                rm -r docs-on-pagure/*
                cp -r docs/_build/html/* docs-on-pagure/
                cd docs-on-pagure
                git add -A .
                if [[ "$(git diff --cached --numstat | wc -l)" -eq 0 ]] ; then
                    exit 0 # No changes, nothing to commit
                fi
                git commit -m 'Automatic commit of docs built by Jenkins job ${env.JOB_NAME} #${env.BUILD_NUMBER}'
                git push origin master
                '''
            }
        }
    }
    stage('Build SRPM') {
        sh './rpmbuild.sh -bs'
        archiveArtifacts artifacts: 'rpmbuild-output/**'
    }
    /* We take a flock on the mock configs, to avoid multiple unrelated jobs on
     * the same Jenkins slave trying to use the same mock root at the same
     * time, which will error out. */
    stage('Build RPM') {
        parallel (
            'EPEL7': {
                sh """
                mkdir -p mock-result/el7
                flock /etc/mock/epel-7-x86_64.cfg \
                /usr/bin/mock --resultdir=mock-result/el7 --no-cleanup-after -r epel-7-x86_64 --clean --rebuild rpmbuild-output/*.src.rpm
                """
                archiveArtifacts artifacts: 'mock-result/el7/**'
            },
            'F25': {
                sh """
                mkdir -p mock-result/f25
                flock /etc/mock/fedora-25-x86_64.cfg \
                /usr/bin/mock --resultdir=mock-result/f25 --no-cleanup-after -r fedora-25-x86_64 --clean --rebuild rpmbuild-output/*.src.rpm
                """
                archiveArtifacts artifacts: 'mock-result/f25/**'
            },
        )
    }
    stage('Invoke Rpmlint') {
        parallel (
            'EPEL7': {
                sh 'rpmlint -f rpmlint-config.py mock-result/el7/*.rpm'
            },
            'F25': {
                sh 'rpmlint -f rpmlint-config.py mock-result/f25/*.rpm'
            },
        )
    }
    /* XXX: run functional tests in OpenShift when UpShift is ready */
}
} catch (e) {
    if (ownership.job.ownershipEnabled) {
        mail to: ownership.job.primaryOwnerEmail,
             cc: ownership.job.secondaryOwnerEmails.join(', '),
             subject: "Jenkins job ${env.JOB_NAME} #${env.BUILD_NUMBER} failed",
             body: "${env.BUILD_URL}\n\n${e}"
    }
    throw e
}
