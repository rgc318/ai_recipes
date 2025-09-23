// Jenkinsfile (声明式流水线) - 无 Docker Hub 部署版本

pipeline {
    // 1. 定义构建环境 (不变)
    agent {
        docker {
            image 'docker:26-cli'
            args '-u root -v /var/run/docker.sock:/var/run/docker.sock'
        }
    }

    // 2. 定义环境变量 (不变)
    environment {
        REGISTRY              = 'rgc318'
        IMAGE_NAME            = 'ai-recipes-app'
        SERVER_USER           = 'vivy'
        SERVER_IP             = '192.168.31.229'
        SERVER_PROJECT_PATH   = '/srv/ai_recipes/backend'
        DOCKER_CREDENTIALS_ID = 'dockerhub-credentials'
        SERVER_CREDENTIALS_ID = 'server-ssh-key'
    }

    // 3. 定义构建阶段
    stages {
        stage('Welcome') {
            steps {
                echo "🚀 开始为镜像 ${env.REGISTRY}/${env.IMAGE_NAME} 执行 CI/CD 流水线 (无 Registry 模式)..."
            }
        }

        stage('Build and Save Application Image') { // 阶段名稍作修改
            steps {
                script {
                    // 定义镜像标签和打包后的文件名
                    env.IMAGE_TAG = "build-${BUILD_NUMBER}"
                    env.IMAGE_FILENAME = "${env.IMAGE_NAME}-${env.IMAGE_TAG}.tar"
                }

                // 构建镜像
                sh "docker build -t ${env.REGISTRY}/${env.IMAGE_NAME}:${env.IMAGE_TAG} ."
                sh "docker tag ${env.REGISTRY}/${env.IMAGE_NAME}:${env.IMAGE_TAG} ${env.REGISTRY}/${env.IMAGE_NAME}:latest"

                // 将镜像打包成 tar 文件
                echo "--- 正在将镜像打包为 ${env.IMAGE_FILENAME} ---"
                sh "docker save -o ${env.IMAGE_FILENAME} ${env.REGISTRY}/${env.IMAGE_NAME}:${env.IMAGE_TAG}"
            }
        }

        // Push 阶段可以彻底删除或保持注释

        stage('Deploy to Server') {
            steps {
                echo "--- 准备通过 SSH 部署到服务器 ${env.SERVER_IP} ---"
                withCredentials([sshUserPrivateKey(credentialsId: env.SERVER_CREDENTIALS_ID, keyFileVariable: 'SSH_KEY')]) {
                    sshagent (credentials: [env.SERVER_CREDENTIALS_ID]) {

                        // 1. 使用 scp 将镜像包传输到服务器
                        echo "--- 正在传输镜像包 ${env.IMAGE_FILENAME} 到服务器 ---"
                        // 注意: 这里也去掉了 -o StrictHostKeyChecking=no，建议提前配置好 known_hosts
                        sh "scp -o StrictHostKeyChecking=no ./${env.IMAGE_FILENAME} ${env.SERVER_USER}@${env.SERVER_IP}:${env.SERVER_PROJECT_PATH}/${env.IMAGE_FILENAME}"

                        // 2.【新增!】传输最新的 docker-compose.yml 文件
                        echo "--- 正在同步最新的 docker-compose.yml 文件 ---"
                        sh "scp -o StrictHostKeyChecking=no ./docker-compose.yml ${env.SERVER_USER}@${env.SERVER_IP}:${env.SERVER_PROJECT_PATH}/docker-compose.yml"

                        // 2. SSH 到服务器执行加载和部署命令
                        echo "--- 正在服务器上加载镜像并重启服务 ---"
                        sh """
                            ssh -o 'StrictHostKeyChecking=no' ${env.SERVER_USER}@${env.SERVER_IP} 'bash -s' << 'EOF'
                                echo "✅ 成功登录到服务器！"

                                # 进入你的项目目录
                                echo "--- 正在进入项目目录: ${env.SERVER_PROJECT_PATH} ---"
                                cd ${env.SERVER_PROJECT_PATH}

                                # 从 tar 文件加载镜像
                                echo "--- 正在从 ${env.IMAGE_FILENAME} 加载镜像 ---"
                                docker load -i ${env.IMAGE_FILENAME}

                                # 删除已传输的 tar 包，节省空间
                                rm ${env.IMAGE_FILENAME}

                                # 直接使用新加载的镜像重新启动服务
                                echo "--- 正在使用新镜像重启服务 ---"
                                docker compose up -d --remove-orphans app

                                # （可选）清理旧的、未使用的镜像
                                echo "--- 正在清理旧镜像 ---"
                                docker image prune -af

                                echo "🎉 部署成功！"
EOF
                        """
                    }
                }
            }
        }
    }

    // 4. 定义构建后操作
    post {
        always {
            echo "--- 清理工作环境 ---"
            // 清理 Jenkins 工作区中生成的 tar 包
            sh "rm -f *.tar"
        }
    }
}
