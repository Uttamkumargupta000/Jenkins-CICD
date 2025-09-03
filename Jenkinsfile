// Define job parameters (using Extended Choice for SERVICES)
properties([
    parameters([
        [$class: 'ExtendedChoiceParameterDefinition',
         name: 'SERVICES',
         description: 'Select the services (repositories) to update (use Ctrl/Command-click for multiple selections)',
         type: 'PT_MULTI_SELECT',
         multiSelectDelimiter: ',',
         visibleItemCount: 8,
         value: 'gripinvest/grip-client-backend,gripinvest/grip-client-web,gripinvest/gi-client-static,gripinvest/gi-client-web,gripinvest/gi-sirius,gripinvest/gi-strapi-cms,gripinvest/grip-terminal-web,gripinvest/gi-partner-portal'
        //  value: 'gripinvest/release-test-1,gripinvest/release-test-2,grip/gi-sirius,gripinvest/metabase-ai-bot-ui'
        ]
    ])
])


// Use a designated agent/node
node('gi-jenkins-master') {
    // Declare local variables
    def BASE_BRANCH_NAME
    def RELEASE_TAG_NAME
    // The SERVICES parameter is defined as a job property and is available via params.SERVICES.
    def SELECTED_SERVICES = params.SERVICES
    def extractedList = []
    def successServicesList = []
    def lastLine
    def localBasePath = "C:\\production_cic"
    def releaseTestRepo = "gripinvest/jenkins-production-cicd"
    def releaseTestDir = "${localBasePath}\\jenkins-production-cicd"
    def output = ''

    stage('Manual Input') {
        script {
            // Stage 1: Prompt for release branch and tag names.
            BASE_BRANCH_NAME = input(
                message: 'Enter the Base Branch For Release to cut:',
                parameters: [
                    string(name: 'ReleaseBranchName', defaultValue: 'develop', description: 'Name of the release branch')
                ]
            )
            echo "Release Base branch name: ${BASE_BRANCH_NAME}"
            
            RELEASE_TAG_NAME = input(
                message: 'Enter the release tag name:',
                parameters: [
                    string(name: 'ReleaseTagName', defaultValue: 'v1.0.0', description: 'Name of the release tag')
                ]
            )
            echo "Release tag name: ${RELEASE_TAG_NAME}"
        }
    }

    stage('Select Services') {
        script {
            echo "Selected services: ${SELECTED_SERVICES}"
        }
    }

    stage('Production Build Approval') {
        script {
            // Stage 3: Pause for production build approval.
            def allowedApprovers = ['prayas_mittal', 'utkarsh_khandelwal', 'uttam']
            def approver = input(message: 'Do you approve the build?', submitterParameter: 'approver')
            if (!allowedApprovers.contains(approver)) {
                error "Unauthorized approver: ${approver}"
            }
            echo "Approved by: ${approver}"
        }
    }
    
    stage('Build New Release') {
      script {
          try {
              withCredentials([string(credentialsId: 'GITHUB_TOKEN', variable: 'GITHUB_TOKEN')]) {
                  // Step 1: Ensure base directory exists
                  echo "Checking and creating base directory if not present: ${localBasePath}"
                  bat "IF NOT EXIST \"${localBasePath}\" mkdir \"${localBasePath}\""

                  // Check if repository directory already exists
                  echo "Checking if repository directory exists: ${releaseTestDir}"
                  def repoExistsRaw = bat(script: "IF EXIST \"${releaseTestDir}\" (echo YES) ELSE (echo NO)", returnStdout: true).trim()
                  def repoExists = repoExistsRaw.readLines().last().trim()
                  echo "Repository exists: ${repoExists}"

                  def pullSuccess = false

                  if (repoExists == "YES") {
                      echo "Repo Directory exists Attempting to pull changes.: ${releaseTestDir}"

                      def pullStatus = bat(script: """
                            cd \"${releaseTestDir}\"
                            git fetch origin
                            git checkout ${BASE_BRANCH_NAME}
                            git reset --hard origin/${BASE_BRANCH_NAME}
                            git clean -fd
                        """, returnStatus: true)

                      if (pullStatus == 0){
                        echo "Successfully Pulled the latest changes."
                        pullSuccess = true
                      } else {
                        echo "Pull failed. Will remove and re-clone."
                        def deleteStatus = bat(script: "rmdir /S /Q \"${releaseTestDir}\"", returnStatus: true)
                        if (deleteStatus != 0) {
                            error "Failed to delete directory: ${releaseTestDir}. It might be locked or in use."
                        }
                        echo "Directory deleted successfully."
                      }
                  }
                  
                  if (repoExists == "NO" || !pullSuccess) {
                    echo "Cloning repository ${releaseTestRepo} into ${releaseTestDir}"
                    bat """
                        set GITHUB_TOKEN=${GITHUB_TOKEN}
                        git clone https://%GITHUB_TOKEN%@github.com/${releaseTestRepo}.git \"${releaseTestDir}\"
                        cd \"${releaseTestDir}\"
                        git checkout ${BASE_BRANCH_NAME}
                    """
                  }
                  echo "Running Python script to create tag/release for services: ${SELECTED_SERVICES}"
                  output = bat(script: "python \"${releaseTestDir}\\Production_release_newtest.py\" \"${BASE_BRANCH_NAME}\" \"${RELEASE_TAG_NAME}\" \"${SELECTED_SERVICES}\" \"%GITHUB_TOKEN%\"", returnStdout: true, wait: true).trim()

                  echo "Python script output:\n${output}"

                  // Extract the last line and process JSON-like list
                  // lastLine = output.readLines().last()
                  // extractedList = lastLine.replaceAll("\\[|\\]", "").replaceAll("\"", "").trim().tokenize(',').collect { it.trim() }
                  lastLine = output.readLines().last()
                  echo "Last line from Python output: '${lastLine}'"

                  extractedList = lastLine
                      .replaceAll("\\[|\\]", "")     // remove brackets
                      .replaceAll("\"", "")          // remove quotes
                      .trim()
                      .tokenize(',')
                      .collect { it.trim().replace("gripinvest/", "") }  // REMOVE gripinvest/

                  echo "Extracted repos for release: ${extractedList}"

                  if (!extractedList || extractedList.isEmpty()) {
                      echo "No repository found. Skipping new tag creation."
                  } else {
                      // Generate links assuming 'gripinvest' is the owner
                      def baseUrl = "https://github.com/gripinvest/"
                      def links = extractedList.collect { repoName ->
                          "${baseUrl}${repoName}/pkgs/container/${repoName}"
                      }
                      def generatedLinks = links.join(', ')

                      echo "Generated release links:\n${generatedLinks}"
                  }
              }
          } catch (Exception e) {
              error "Python Script execution failed: ${e.getMessage()}"
          }
      }
  }

  stage('Wait for GitHub Action') {
    //   wait for 30 sec before executing the logic 
      sleep(time: 30, unit: 'SECONDS')
    // Skip if nothing to monitor
    if (!extractedList) {
      echo "No repos to monitor; skipping."
    } else {
      int maxAttempts    = 20      // ~15 minutes @ 30s intervals
      int intervalSecond = 50

      withCredentials([ string(credentialsId: 'GITHUB_TOKEN', variable: 'GH_TOKEN') ]) {
        extractedList.each { repo -> 
          repo = repo.trim()
          echo "Monitoring GitHub Action for tag '${RELEASE_TAG_NAME}' in ${repo}"
          boolean success = false
          for (int i = 1; i <= maxAttempts; i++) {
            echo "Attempt ${i}/${maxAttempts}"
            def resp = httpRequest(
              httpMode: 'GET',
              url: "https://api.github.com/repos/gripinvest/${repo}/actions/workflows/production-release.yml/runs?ref=${RELEASE_TAG_NAME}&per_page=1",
              customHeaders: [
                [name: 'Authorization', value: "token ${GH_TOKEN}"],
                [name: 'Accept',        value: 'application/vnd.github.v3+json']
              ],
              validResponseCodes: '200'
            )
            def runs = readJSON(text: resp.content).workflow_runs ?: []
            if (!runs) {
              echo "No runs yet for 'build.yml'with ref='${RELEASE_TAG_NAME}'"
            } else {
              def run = runs[0]
              echo "Status='${run.status}', conclusion='${run.conclusion}'"
              echo "Github Action URL : ${run.html_url}"
              if (run.status == 'completed') {
                if (run.conclusion == 'success') {
                  echo "GitHub Action succeeded for ${repo}"
                  success = true
                  break
                } else {
                  error "GitHub Action failed for ${repo} (conclusion=${run.conclusion})\nSee: ${run.html_url}"
                }
              }
            }
            sleep(time: intervalSecond, unit: 'SECONDS')
          }

          if (!success) {
            error "Timed out waiting for GitHub Action for ${repo}"
          }
        }
      }
    }
  }
    
    stage('Download and Extract the Github Artifact'){
      if (params.SERVICES?.split(',')?.collect { it.trim() }?.contains('gripinvest/gi-sirius')) {
          script {
            def repo = "gripinvest/gi-sirius"
            def workflowFile = "production-release.yml"
            def artifactName = "Success-Service"
            def downloadDir = "C:\\production_cic"

            // Ensure directory exist
            powershell """
                if (-Not (Test-Path -Path '${downloadDir}')) {
                  New-Item -ItemType Directory -Path '${downloadDir}' | Out-Null
                }
              """
              // Clean up older Zip files
              powershell """
                \$files = Get-ChildItem -Path '${downloadDir}' -Recurse -Include *.zip | Sort-Object LastWriteTime -Descending
                \$files | Select-Object -Skip 5 | Remove-Item -Force
              """

              // Fetch Artifact 
              withCredentials([string(credentialsId: 'GITHUB_TOKEN', variable: 'GITHUB_TOKEN')]) {
                def runId = powershell(
                  script: """
                    \$headers =  @{Authorization = 'Bearer ${GITHUB_TOKEN}'}
                    \$uri = "https://api.github.com/repos/${repo}/actions/workflows/${workflowFile}/runs?status=success&per_page=1"
                    \$response = Invoke-RestMethod -Headers \$headers -Uri \$uri
                    \$response.workflow_runs[0].id
                  """,
                  returnStdout: true
                ).trim()

                echo "GitHub Run ID: ${runId}"

                // wokflow-action_id for test = 15308289148
                def artifactUrl = powershell(
                  script: """
                    \$headers = @{ Authorization = "Bearer \$env:GITHUB_TOKEN" }
                    \$uri = "https://api.github.com/repos/${repo}/actions/runs/${runId}/artifacts"
                    Write-Host "Fetching artifact list from: \$uri"
                    \$response = Invoke-RestMethod -Headers \$headers -Uri \$uri
                    \$artifact = \$response.artifacts | Where-Object { \$_.name -eq '${artifactName}' }
                    if (-not \$artifact) {
                      Write-Error "Artifact named '${artifactName}' not found."
                      exit 1
                    }
                    \$artifact.archive_download_url
                  """,
                  returnStdout: true
                ).trim()

                echo "Artifact URL: ${artifactUrl}"
                def zipPath = "${downloadDir}/artifact-${runId}.zip"
                def extractPath = "${downloadDir}\\artifact-${runId}"

                powershell """
                  \$token = "\$env:GITHUB_TOKEN"
                  \$headers = @{ Authorization = "Bearer \$token" }
                  Invoke-WebRequest -Uri '${artifactUrl}' -Headers \$headers -OutFile '${zipPath}' -UseBasicParsing
                """
                // Extract zip
                extractPath = "${downloadDir}/artifact-${runId}"
                powershell """
                  Expand-Archive -Path '${zipPath}' -DestinationPath '${extractPath}' -Force
                """
                // Read values into a global variable list
                def txtPath = "${extractPath}\\success-service.txt"
                def serviceText = powershell(
                  script: "Get-Content -Path '${txtPath}' -Raw",
                  returnStdout: true
                ).trim()

                successServicesList = serviceText.split('\n').collect { it.trim() }
                echo "Extracted Services: ${successServicesList}"
              }
          }
        }
        else {
          echo "skipping artifact download because service condition is not met"
        }
    }

    stage('Set Git Identity') {
            script {
                bat '''
                git config --global user.email "utkarsh.khandelwal@gripinvest.in"
                git config --global user.name "utkarsh khandelwal"
                '''
            }
        }
    stage('Deployment Stage') {
        script {
            def allowedApprovers = ['prayas_mittal', 'utkarsh_khandelwal' , 'uttam']
            def approver = input(message: 'Do you approve the build?', submitterParameter: 'approver')
            if (!allowedApprovers.contains(approver)) {
                error "Unauthorized approver: ${approver}"
            }
            echo "Approved by: ${approver}"

            // Clean both lists and remove 'gripinvest/' prefix and 'gi-sirius' repo
            def cleanList = { list ->
                if (list == null) return []
                return list.collect { it.trim().replace("gripinvest/", "") }
                          .findAll { it && it != "gi-sirius" }
            }
            def cleanedExtractedList = cleanList(extractedList)
            def cleanedSuccessServicesList = cleanList(successServicesList)

            // Combine and remove duplicates
            def combinedServices = (cleanedExtractedList + cleanedSuccessServicesList).unique()
            def joinedServices = combinedServices.join(',')

            if (combinedServices.isEmpty()) {
                echo "No services to deploy after filtering."
            } else {
                echo "Final services to deploy: ${joinedServices}"

                withCredentials([string(credentialsId: 'GITHUB_TOKEN', variable: 'GITHUB_TOKEN')]){
                    def result = bat(script: "python \"${releaseTestDir}\\production_deployment_all.py\" \"${RELEASE_TAG_NAME}\" \"${joinedServices}\" \"%GITHUB_TOKEN%\"", returnStdout: true).trim()
                    echo result
                }
            }
        }
    }

    // }
    // stage('Notify Team'){
    //     script{
    //         try{
    //             // slack Notification
    //             echo "Sending Message to slack ..."
    //             slackSend(channel: '#releases', message: "Production release ${RELEASE_TAG_NAME} completed for : ${SELECTED_SERVICES}")

    //             // EMAIL NOTIFICATION
    //             emailext(
    //                 subject: "Production release ${RELEASE_TAG_NAME} Completed!",
    //                 body: """<p> The following services have been updated in Production: <p>
    //                 <ul> ${SELECTED-SERVICES.split(',).collect {"<li>${it}</li>"}.join('')}</ul>
    //                 <p>Deployment completed successfully. </p>""",
                    
    //                 receipientProviders: [[$class: 'CulpritsRecipientProvider'], [$class: 'RequesterRecipientProvider']], to: 'xyz@gripinvest.in'
    //             )
    //         }
    //         catch (Exception e){
    //             // Slack Notification Failure
    //             slackSend(channel: '#release', message: 'Failure! Production release `${RELEASE_TAG_NAME}` Failed for : `${SELECTED_SERVICES}`. Check Logs!')

    //             // Email Notification Failure
    //             emailext(
    //                 subject: "Failure : Production Release ${RELEASE_TAG_NAME} Failed!",
    //                 body: """<p>The Following services failed during deployment: </p>
    //                 <ul> #{SELECTED_SERVICES.split(',').collect {"<li>${it}</li>"}.join('')}</ul>
    //                 <p>Status: Deployment Failed. Please check the Logs for more details.</p>"""
    //                 receipientProviders:[[$class: 'CulpritsRecipientProviders'], [$class: 'RequestRecipientProvider']], to: 'xyz@gripinvest.in, pqrs@gripinvest.in'
    //             )
    //             error "Deployment failed. sending failure Notification."
    //         }
    //     }
    // }
}

def generateLinks(extractedList) {
    if(!extractedList || extractedList.isEmpty()){
        echo "No Valid repository found to generate links"
        return ""
    }
    def baseUrl = "https://github.com/"
    def links = extractedList.collect { service ->
        // Split the service name into owner and repo
        def (owner, repo) = service.trim().split('/')
        // Generate the link
        return "${baseUrl}${owner}/${repo}/pkgs/container/${repo}"
    }

    def joinedLinks = links.join(', ')
    // Print the generated links
    echo "Generated Link: ${joinedLinks}" 
    return joinedLinks
}

