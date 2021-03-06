/*
 * SPDX-License-Identifier: GPL-2.0+
 */
import groovy.json.*

// 'global' var to store git info
def scmVars

// Greenwave RPM dependencies
def installDepsCmd = '''
sudo dnf -y install \
    python3-dogpile-cache \
    python3-fedmsg \
    python3-fedora-messaging \
    python3-flask \
    python3-prometheus_client \
    python3-PyYAML \
    python3-requests
'''.trim()

try { // massive try{} catch{} around the entire build for failure notifications

node('master'){
    scmVars = checkout scm
    scmVars.GIT_BRANCH_NAME = scmVars.GIT_BRANCH.split('/')[-1]  // origin/pr/1234 -> 1234

    // setting build display name
    def branch = scmVars.GIT_BRANCH_NAME
    if ( branch == 'master' ) {
        echo 'Building master'
    }
    else if (branch ==~ /[0-9]+/) {
        def pagureUrl = "https://pagure.io/greenwave/pull-request/${branch}"
        def pagureLink = """<a href="${pagureUrl}">PR-${branch}</a>"""
        try {
            def response = httpRequest "https://pagure.io/api/0/greenwave/pull-request/${branch}"
            // Note for future use: JsonSlurper() is not serialiazble (returns a LazyMap) and
            // therefore we cannot save this back into the global scmVars. We could use
            // JsonSlurperClassic() which returns a hash map, but would need to allow this in
            // the jenkins script approval.
            def content = new JsonSlurper().parseText(response.content)
            pagureLink = """<a href="${pagureUrl}">${content.title}</a>"""
        } catch (Exception e) {
            echo 'Error using pagure API:'
            echo e.message
            // ignoring this...
        }
        echo "Building PR #${branch}: ${pagureUrl}"
        currentBuild.displayName = "PR #${branch}"
        currentBuild.description = pagureLink
    }
}

timestamps {
node('fedora-29') {
    checkout scm
    scmVars.GIT_AUTHOR_EMAIL = sh (
        script: 'git --no-pager show -s --format=\'%ae\'',
        returnStdout: true
    ).trim()

    sh """
    ${installDepsCmd}
    sudo dnf -y install python3-flake8 python3-pylint python3-sphinx \
        python3-sphinxcontrib-httpdomain python3-pytest-cov mock-core-configs
    """
    /* Needed to get the latest /etc/mock/fedora-28-x86_64.cfg */
    sh 'sudo dnf -y update mock-core-configs'
    stage('Invoke Flake8') {
        sh 'flake8-3'
    }
    stage('Invoke Pylint') {
        sh 'pylint-3 --reports=n greenwave'
    }
    stage('Run unit tests') {
        sh '''
        rm -rf htmlcov coverage.xml
        pytest-3 greenwave/tests/ \
            --cov-config .coveragerc --cov=greenwave \
            --cov-report term --cov-report xml --cov-report html
        '''
        archiveArtifacts artifacts: 'htmlcov/**,coverage.xml'
        step([
            $class: 'CoberturaPublisher',
            autoUpdateHealth: false,
            autoUpdateStability: false,
            coberturaReportFile: 'coverage.xml',
            failUnhealthy: false,
            failUnstable: false,
            maxNumberOfBuilds: 0,
            onlyStable: false,
            zoomCoverageChart: false
        ])
    }
    stage('Build Docs') {
        sh '''
        sudo dnf install -y \
            python3-sphinx \
            python3-sphinxcontrib-httpdomain \
            make
        '''
        sh 'DEV=true GREENWAVE_CONFIG=$(pwd)/conf/settings.py.example make -C docs html'
        archiveArtifacts artifacts: 'docs/_build/html/**'
    }
    if (scmVars.GIT_BRANCH == 'origin/master') {
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
                git config user.name "Jenkins Job"
                git config user.email "nobody@redhat.com"
                git commit -m 'Automatic commit of docs built by Jenkins job ${env.JOB_NAME} #${env.BUILD_NUMBER}'
                git push origin master
                '''
            }
        }
    }
}

node('fedora-29') {
    checkout scm

    /* Install packages needed by the functional tests. */
    sh 'sudo dnf -y install python3-pytest python3-requests python3-sqlalchemy python3-gunicorn'

    /* Also need to install Greenwave's dependencies, since we are running it
     * locally not in Openshift for now. */
    sh installDepsCmd

    def openshiftHost = 'greenwave-test.cloud.paas.psi.redhat.com'
    def buildTag = "${env.BUILD_TAG}".replace('jenkins-','')
    def waiverdbURL = "waiverdb-test-${buildTag}-web-${openshiftHost}"
    def resultsdbURL = "resultsdb-test-${buildTag}-api-${openshiftHost}"

    def resultsdbRepo = 'https://pagure.io/taskotron/resultsdb/raw/develop/f/openshift'
    def resultsdbTemplate = 'resultsdb-test-template.yaml'
    sh "curl ${resultsdbRepo}/${resultsdbTemplate} > openshift/${resultsdbTemplate}"

    def waiverdbRepo = 'https://pagure.io/waiverdb/raw/master/f/openshift'
    def waiverdbTemplate = 'waiverdb-test-template.yaml'
    sh "curl ${waiverdbRepo}/${waiverdbTemplate} > openshift/${waiverdbTemplate}"

    stage('Perform functional tests') {
        openshift.withCluster('psi') {
            openshift.withCredentials('psi-greenwave-test-jenkins-credentials') {
                openshift.withProject('greenwave-test') {
                    def rtemplate = readYaml file: 'openshift/resultsdb-test-template.yaml'
                    // TODO: move this image to the factory2 project in the docker registry
                    def resultsdbImage = 'quay.io/factory2/resultsdb:latest'
                    def resultsdbModels = openshift.process(
                        rtemplate,
                        '-p', "TEST_ID=${buildTag}",
                        '-p', "RESULTSDB_IMAGE=${resultsdbImage}",
                        '-p', "RESULTSDB_ADDITIONAL_RESULT_OUTCOMES=\"('RUNNING','QUEUED')\""
                    )
                    def wtemplate = readYaml file: 'openshift/waiverdb-test-template.yaml'
                    def waiverdbModels = openshift.process(
                        wtemplate,
                        '-p', "TEST_ID=${buildTag}",
                        '-p', 'WAIVERDB_APP_IMAGE=quay.io/factory2/waiverdb:latest',
                        '-p', "RESULTSDB_API_URL=${resultsdbURL}",
                        '-p', "WAIVERDB_REPLICAS=1"
                    )
                    def environment_label = "test-${buildTag}"
                    try {
                        openshift.create(resultsdbModels)
                        openshift.create(waiverdbModels)
                        echo "Waiting for pods with label environment=${environment_label} to become Ready"
                        def pods = openshift.selector('pods', ['environment': environment_label])
                        timeout(10) {
                            pods.untilEach(5) {
                                def conds = it.object().status.conditions
                                for (int i = 0; i < conds.size(); i++) {
                                    if (conds[i].type == 'Ready' && conds[i].status == 'True') {
                                        return true
                                    }
                                }
                                return false
                            }
                        }

                        timeout(15) { // minutes
                        def route_hostname = waiverdbURL
                        echo "Fetching CA chain for https://${route_hostname}/"
                        def ca_chain = sh(returnStdout: true, script: """openssl s_client \
                                -connect ${route_hostname}:443 \
                                -servername ${route_hostname} -showcerts < /dev/null | \
                                awk 'BEGIN {first_cert=1; in_cert=0};
                                    /BEGIN CERTIFICATE/ { if (first_cert == 1) first_cert = 0; else in_cert = 1 };
                                    { if (in_cert) print };
                                    /END CERTIFICATE/ { in_cert = 0 }'""")
                        writeFile(file: "${env.WORKSPACE}/ca-chain.crt", text: ca_chain)
                        echo "Wrote CA certificate chain to ${env.WORKSPACE}/ca-chain.crt"

                        withEnv(["GREENWAVE_CONFIG=${env.WORKSPACE}/conf/settings.py.example"
                                ,"PYTHONPATH=."
                                ,"REQUESTS_CA_BUNDLE=${env.WORKSPACE}/ca-chain.crt"
                                ,"WAIVERDB_TEST_URL=https://${waiverdbURL}/"
                                ,"RESULTSDB_TEST_URL=https://${resultsdbURL}/"]) {
                            sh 'py.test-3 -v --junitxml=junit-functional-tests.xml functional-tests/'
                        }
                        junit 'junit-functional-tests.xml'
                        }  //end timeout
                    } finally {
                        /* Extract logs for debugging purposes */
                        openshift.selector('deploy,pods', ['environment': environment_label]).logs()
                        /* Tear down everything we just created */
                        openshift.selector('dc,deploy,configmap,secret,svc,route',
                                ['environment': environment_label]).delete()
                    }
                }
            }
        }
    }
}

} // end of timestamps
} catch (e) {
    // since the result isn't set until after the pipeline script runs, we must set it here if it fails
    currentBuild.result = 'FAILURE'
    throw e
} finally {
    // if result hasn't been set to failure by this point, its a success.
    def currentResult = currentBuild.result ?: 'SUCCESS'
    def branch = scmVars.GIT_BRANCH_NAME

    // send pass/fail email
    def SUBJECT = ''
    if ( branch ==~ /[0-9]+/) {
        if (currentResult == 'FAILURE' ){
            SUBJECT = "Jenkins job ${env.JOB_NAME}, PR #${branch} failed."
        } else {
            SUBJECT = "Jenkins job ${env.JOB_NAME}, PR #${branch} passed."
        }
    } else if (currentResult == 'FAILURE') {
        SUBJECT = "Jenkins job ${env.JOB_NAME} #${env.BUILD_NUMBER} failed."
    }

    def RECIEPENT = scmVars.GIT_AUTHOR_EMAIL
    if (ownership.job.ownershipEnabled && branch == 'master') {
        RECIEPENT = ownership.job.primaryOwnerEmail
    }

    def BODY = "Build URL: ${env.BUILD_URL}"
    if (branch ==~ /[0-9]+/){
        BODY = BODY + "\nPull Request: https://pagure.io/greenwave/pull-request/${branch}"
    }

    if (SUBJECT != '') {
        emailext to: RECIEPENT,
                 subject: SUBJECT,
                 body: BODY
    }

    // update Pagure PR status
    if (branch ==~ /[0-9]+/) {  // PR's will only be numbers on pagure
        def resultPercent = (currentResult == 'SUCCESS') ? '100' : '0'
        def resultComment = (currentResult == 'SUCCESS') ? 'Build passed.' : 'Build failed.'
        def pagureRepo = new URL(scmVars.GIT_URL).getPath() - ~/^\// - ~/.git$/  // https://pagure.io/my-repo.git -> my-repo

        withCredentials([string(credentialsId: "${env.PAGURE_API_TOKEN}", variable: 'TOKEN')]) {
        build job: 'pagure-PR-status-updater',
            propagate: false,
            parameters: [
                // [$class: 'StringParameterValue', name: 'PAGURE_REPO', value: 'https://pagure.io'],  // not needed if https://pagure.io
                [$class: 'StringParameterValue', name: 'PAGURE_PR', value: branch],
                [$class: 'StringParameterValue', name: 'PAGURE_REPO', value: pagureRepo],
                [$class: 'StringParameterValue', name: 'PERCENT_PASSED', value: resultPercent],
                [$class: 'StringParameterValue', name: 'COMMENT', value: resultComment],
                [$class: 'StringParameterValue', name: 'REFERENCE_URL', value: "${env.BUILD_URL}"],
                [$class: 'StringParameterValue', name: 'REFERENCE_JOB_NAME', value: "${env.JOB_NAME}"],
                [$class: 'hudson.model.PasswordParameterValue', name: 'TOKEN', value: "${env.TOKEN}"]
                        ]
        }
    }
}
