/*
 * SPDX-License-Identifier: GPL-2.0+
 */

// 'global' var to store git info
def scmVars

try { // massive try{} catch{} around the entire build for failure notifications

node('master'){
    scmVars = checkout scm
}

timestamps {
node('fedora-27') {
    checkout scm
    sh 'sudo dnf -y builddep greenwave.spec'
    sh 'sudo dnf -y install python3-flake8 python3-pylint python3-sphinx python3-sphinxcontrib-httpdomain'
    /* Needed to get the latest /etc/mock/fedora-28-x86_64.cfg */
    sh 'sudo dnf -y update mock-core-configs'
    stage('Invoke Flake8') {
        sh 'flake8-3'
    }
    stage('Invoke Pylint') {
        sh 'pylint-3 --reports=n greenwave'
    }
    stage('Build Docs') {
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
            'F27': {
                sh """
                mkdir -p mock-result/f27
                flock /etc/mock/fedora-27-x86_64.cfg \
                /usr/bin/mock -v --enable-network --resultdir=mock-result/f27 -r fedora-27-x86_64 --clean --rebuild rpmbuild-output/*.src.rpm
                """
                archiveArtifacts artifacts: 'mock-result/f27/**'
            },
            'F28': {
                sh """
                mkdir -p mock-result/f28
                flock /etc/mock/fedora-28-x86_64.cfg \
                /usr/bin/mock -v --enable-network --resultdir=mock-result/f28 -r fedora-28-x86_64 --clean --rebuild rpmbuild-output/*.src.rpm
                """
                archiveArtifacts artifacts: 'mock-result/f28/**'
            },
        )
    }
    stage('Invoke Rpmlint') {
        parallel (
            'F27': {
                sh 'rpmlint -f rpmlint-config.py mock-result/f27/*.rpm'
            },
            'F28': {
                sh 'rpmlint -f rpmlint-config.py mock-result/f28/*.rpm'
            },
        )
    }
}
node('docker') {
    checkout scm
    stage('Build Docker container') {
        unarchive mapping: ['mock-result/f28/': '.']
        def f28_rpm = findFiles(glob: 'mock-result/f28/**/*.noarch.rpm')[0]
        def appversion = sh(returnStdout: true, script: """
            rpm2cpio ${f28_rpm} | \
            cpio --quiet --extract --to-stdout ./usr/lib/python3\\*/site-packages/greenwave\\*.egg-info/PKG-INFO | \
            awk '/^Version: / {print \$2}'
        """).trim()
        /* Git builds will have a version like 0.3.2.dev1+git.3abbb08 following
         * the rules in PEP440. But Docker does not let us have + in the tag
         * name, so let's munge it here. */
        appversion = appversion.replace('+', '-')
        docker.withRegistry(
                'https://docker-registry.engineering.redhat.com/',
                'docker-registry-factory2-builder-sa-credentials') {
            /* Note that the docker.build step has some magic to guess the
             * Dockerfile used, which will break if the build directory (here ".")
             * is not the final argument in the string. */
            def image = docker.build "factory2/greenwave:internal-${appversion}", "--build-arg greenwave_rpm=$f28_rpm --build-arg cacert_url=https://password.corp.redhat.com/RH-IT-Root-CA.crt ."
            /* Pushes to the internal registry can sometimes randomly fail
             * with "unknown blob" due to a known issue with the registry
             * storage configuration. So we retry up to 3 times. */
            retry(3) {
                image.push()
            }
        }
        /* Build and push the same image with the same tag to quay.io, but without the cacert. */
        docker.withRegistry(
                'https://quay.io/',
                'quay-io-factory2-builder-sa-credentials') {
            def image = docker.build "factory2/greenwave:${appversion}", "--build-arg greenwave_rpm=$f28_rpm ."
            image.push()
        }
        /* Save container version for later steps (this is ugly but I can't find anything better...) */
        writeFile file: 'appversion', text: appversion
        archiveArtifacts artifacts: 'appversion'
    }
}

node('fedora-27') {
    checkout scm

    /* Install packages needed by the functional tests. */
    sh 'sudo dnf -y install python3-pytest python3-requests python3-sqlalchemy python3-gunicorn'

    /* Also need to install Greenwave's dependencies, since we are running it
     * locally not in Openshift for now. */
    sh 'sudo dnf -y builddep greenwave.spec'

    def openshiftHost = 'greenwave-test.cloud.upshift.engineering.redhat.com'
    def waiverdbURL = "waiverdb-test-${env.BUILD_TAG}-web-${openshiftHost}"
    def resultsdbURL = "resultsdb-test-${env.BUILD_TAG}-api-${openshiftHost}"

    def resultsdbRepo = 'https://pagure.io/taskotron/resultsdb/raw/develop/f/openshift'
    def resultsdbTemplate = 'resultsdb-test-template.yaml'
    sh "curl ${resultsdbRepo}/${resultsdbTemplate} > openshift/${resultsdbTemplate}"

    def waiverdbRepo = 'https://pagure.io/waiverdb/raw/master/f/openshift'
    def waiverdbTemplate = 'waiverdb-test-template.yaml'
    sh "curl ${waiverdbRepo}/${waiverdbTemplate} > openshift/${waiverdbTemplate}"

    stage('Perform functional tests') {
        openshift.withCluster('Upshift') {
            openshift.doAs('upshift-greenwave-test-jenkins-credentials') {
                openshift.withProject('greenwave-test') {
                    def rtemplate = readYaml file: 'openshift/resultsdb-test-template.yaml'
                    // TODO: move this image to the factory2 project in the docker registry
                    def resultsdbImage = 'docker-registry.engineering.redhat.com/csomh/resultsdb:latest'
                    def resultsdbModels = openshift.process(
                        rtemplate,
                        '-p', "TEST_ID=${env.BUILD_TAG}",
                        '-p', "RESULTSDB_IMAGE=${resultsdbImage}"
                    )
                    def wtemplate = readYaml file: 'openshift/waiverdb-test-template.yaml'
                    def waiverdbModels = openshift.process(
                        wtemplate,
                        '-p', "TEST_ID=${env.BUILD_TAG}",
                        '-p', 'WAIVERDB_APP_VERSION=latest',
                        '-p', "RESULTSDB_API_URL=${resultsdbURL}",
                        '-p', "WAIVERDB_REPLICAS=1"
                    )
                    def environment_label = "test-${env.BUILD_TAG}"
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

node('docker') {
    checkout scm
    if (scmVars.GIT_BRANCH == 'origin/master') {
        stage('Tag "latest".') {
            unarchive mapping: ['appversion': 'appversion']
            def appversion = readFile('appversion').trim()
            docker.withRegistry(
                    'https://docker-registry.engineering.redhat.com/',
                    'docker-registry-factory2-builder-sa-credentials') {
                def image = docker.image("factory2/greenwave:internal-${appversion}")
                /* Pushes to the internal registry can sometimes randomly fail
                 * with "unknown blob" due to a known issue with the registry
                 * storage configuration. So we retry up to 3 times. */
                retry(3) {
                    image.push('latest')
                }
            }
            docker.withRegistry(
                    'https://quay.io/',
                    'quay-io-factory2-builder-sa-credentials') {
                def image = docker.image("factory2/greenwave:${appversion}")
                image.push('latest')
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

    // send pass/fail email
    if (ownership.job.ownershipEnabled) {
        def previousResult = currentBuild.previousBuild?.result
        def SUBJECT = ''
        def BODY = "${env.BUILD_URL}"

        if (previousResult == 'FAILURE' && currentResult == 'SUCCESS') {
            SUBJECT = "Jenkins job ${env.JOB_NAME} #${env.BUILD_NUMBER} fixed."
        }
        else if (previousResult == 'SUCCESS' && currentResult == 'FAILURE' ) {
            SUBJECT = "Jenkins job ${env.JOB_NAME} #${env.BUILD_NUMBER} failed."
        }

        if (SUBJECT != '') {
            emailext to: ownership.job.primaryOwnerEmail,
                     subject: SUBJECT,
                     body: BODY
        }
    }

    // update Pagure PR status
    def pagurePR = scmVars.GIT_BRANCH.split('/')[-1]  // origin/pr/1234 -> 1234
    if (pagurePR ==~ /[0-9]+/) {  // PR's will only be numbers on pagure
        def resultPercent = (currentResult == 'SUCCESS') ? '100' : '0'
        def resultComment = (currentResult == 'SUCCESS') ? 'Build passed.' : 'Build failed.'
        def pagureRepo = new URL(scmVars.GIT_URL).getPath() - ~/^\// - ~/.git$/  // https://pagure.io/my-repo.git -> my-repo

        withCredentials([string(credentialsId: "${env.PAGURE_API_TOKEN}", variable: 'TOKEN')]) {
        build job: 'pagure-PR-status-updater',
            propagate: false,
            parameters: [
                // [$class: 'StringParameterValue', name: 'PAGURE_REPO', value: 'https://pagure.io'],  // not needed if https://pagure.io
                [$class: 'StringParameterValue', name: 'PAGURE_PR', value: pagurePR],
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
