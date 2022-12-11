

import os,sys,time,json,shutil
path = os.path.dirname(os.path.abspath(__file__))
app_names=["app1", "animegan", "stable-diffusion",'stable-diffusion-zh-en','cartoon-sd', "paddleocr", "gfpgan", "paddlespeech-asr", "humanseg", "paddlespeech-cls", "ddddocr", "paddlespeech-tts", "yolov3", "deoldify",'chatgpt','speaker-diarization']


# # 生成构建镜像的脚本
# build_file=open('build.sh',mode='w')
# for app_name in app_names:
#     dockerfile_path = os.path.join(app_name,'Dockerfile')
#     app_name = app_name.lower().replace('_', '-')
#     if os.path.exists(dockerfile_path):
#         command = f"docker build -t ccr.ccs.tencentyun.com/cube-studio/aihub:{app_name} ./{app_name}/ && docker push ccr.ccs.tencentyun.com/cube-studio/aihub:{app_name} &"
#         build_file.write(command)
#         build_file.write('\n')
#
# build_file.write('\n\nwait')
# build_file.close()


# =====================#

# 生成内网部署脚本
shutil.rmtree("deploy")
os.makedirs('deploy',exist_ok=True)
env='dev'     # env='dev'    cloud
for app_name in app_names:

    # 内网部署必须要info.json
    info = json.load(open(os.path.join(app_name,'info.json'))) if os.path.exists(os.path.join(app_name,'info.json')) else {"name": app_name}
    dockerfile_path = os.path.join(app_name, 'Dockerfile')

    if env=='cloud':
        synchronous = 'asynchronous'
        resource_gpu = '0'
        host='www.data-master.net'
    else:
        synchronous = 'synchronous'
        resource_gpu = info.get('inference',{}).get('resource_gpu','0')
        host='star.tme.woa.com'

    # 生成k8s部署的脚本
    deploy=f'''
apiVersion: v1
kind: Service
metadata:
  name: aihub-{app_name}
  namespace: aihub
  labels:
    app: aihub-{app_name}
spec:
  ports:
    - name: backend
      port: 8080
      targetPort: 8080
      protocol: TCP
    - name: frontend
      port: 80
      targetPort: 80
      protocol: TCP
  selector:
    app: aihub-{app_name}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: aihub-{app_name}
  namespace: aihub
  labels:
    app: aihub-{app_name}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: aihub-{app_name}
  template:
    metadata:
      name: aihub-{app_name}
      labels:
        app: aihub-{app_name}
        aihub: {'cpu' if resource_gpu=='0' else 'gpu'}
    spec:
      volumes:
        - name: tz-config
          hostPath:
            path: /usr/share/zoneinfo/Asia/Shanghai
        - name: app-data
          hostPath:
            path: /data/k8s/kubeflow/pipeline/workspace/pengluan/cube-studio/aihub/deep-learning/{app_name}
        - name: cube-studio
          hostPath:
            path: /data/k8s/kubeflow/pipeline/workspace/pengluan/cube-studio/aihub/src
        - name: cos-data
          hostPath:
            path: /mnt/aihub
      nodeSelector:
        aihub: {'cpu' if resource_gpu=='0' else 'gpu'}
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 20
              podAffinityTerm:
                labelSelector:
                  matchLabels:
                    aihub: {'cpu' if resource_gpu=='0' else 'gpu'}
                topologyKey: kubernetes.io/hostname
                
      containers:
        - name: aihub-{app_name}
          image: ccr.ccs.tencentyun.com/cube-studio/aihub:{app_name}
          imagePullPolicy: Always  # IfNotPresent
          command: ["bash", "-c", "/src/docker/entrypoint.sh python app.py"]
          securityContext:
            privileged: true
          env:
          - name: APPNAME
            value: {app_name}
          - name: REDIS_URL
            value: redis://:admin@125.124.48.210:6379/0
          - name: REQ_TYPE
            value: {synchronous}
          - name: NVIDIA_VISIBLE_DEVICES
            value: all
          - name: COS_URL
            value: https://cube-studio-1252405198.cos.ap-nanjing.myqcloud.com
          - name: HUGGINGFACE_TOKEN
            value: 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
          volumeMounts:
            - name: tz-config
              mountPath: /etc/localtime
            - name: app-data
              mountPath: /app
            - name: cube-studio
              mountPath: /src
            - name: cos-data
              mountPath: /src/cubestudio/aihub/web/static
          
          readinessProbe:
            failureThreshold: 2
            httpGet:
              path: /{app_name}/info
              port: 80
            initialDelaySeconds: 10
            periodSeconds: 10
            timeoutSeconds: 5

---
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
metadata:
  name: aihub-{app_name}
  namespace: aihub
spec:
  gateways:
  - {"kubeflow/kubeflow-gateway-8080" if env=='cloud' else 'kubeflow/kubeflow-gateway'}
  hosts:
  - "{host}"
  http:
  - match:
    - uri:
        prefix: /{'aihub/' if app_name=='app1' else app_name+"/"}
    route:
    - destination:
        host: aihub-{app_name}.aihub.svc.cluster.local
        port:
          number: 80
        '''
    os.makedirs('deploy',exist_ok=True)
    save_path = f"deploy/{app_name}.yaml"
    # print(save_path)
    file = open(save_path,mode='w')
    file.write(deploy)
    file.close()

#
#
# # 生成docker-compose和nginx config
# docker_compose_str = '''
# version: '3'
# services:
#   aihub:
#     image: nginx
#     restart: unless-stopped
#     ports:
#       - '8888:8888'
#     volumes:
#       - /data/k8s/kubeflow/pipeline/workspace/pengluan/cube-studio/aihub/deep-learning/default.conf:/etc/nginx/conf.d/default.conf
#
#     '''
#
# nginx_str='''
#
# server {
#     listen       8888;
#     server_name  _;
# %s
#
# }
# '''
# nginx_app_str=''
# compose_file = open('docker-compose.yml',mode='w')
# compose_file.write(docker_compose_str)
#
# for app_name in app_names:
#
#     app_docker_compose_str=f'''
#   {app_name}:
#     image: ccr.ccs.tencentyun.com/cube-studio/aihub:{app_name}
#     restart: unless-stopped
#     entrypoint: /src/docker/entrypoint.sh
#     command: ["python", "app.py"]
#     volumes:
#       - /usr/share/zoneinfo/Asia/Shanghai:/etc/localtime
#       - /data/k8s/kubeflow/pipeline/workspace/pengluan/cube-studio/aihub/deep-learning/{app_name}:/app
#       - /data/k8s/kubeflow/pipeline/workspace/pengluan/cube-studio/aihub/src:/src
#       - /mnt/aihub:/src/cubestudio/aihub/web/static
#     environment:
#       APPNAME: '{app_name}'
#       REDIS_URL: 'redis://:admin@125.124.48.210:6379/0'
#       REQ_TYPE: 'asynchronous'
#       NVIDIA_VISIBLE_DEVICES: all
#
#
#     '''
#
#
#     nginx_app_config=f'''
#
#     location {"~* ^/(aihub|app1)" if app_name=='app1' else "/%s"%app_name}/ {{
#         proxy_pass http://{app_name};
#
#         proxy_http_version 1.1;
#         proxy_set_header Host       $http_host;
#         proxy_set_header        X-Real-IP $remote_addr;
#         proxy_set_header        X-Forwarded-For $proxy_add_x_forwarded_for;
#
#         client_max_body_size     50m;
#         client_body_timeout      5m;
#         proxy_connect_timeout     60s;
#         proxy_read_timeout      5m;
#         proxy_send_timeout      5m;
#
#     }}
#
#     '''
#     compose_file.write(app_docker_compose_str)
#     nginx_app_str+=nginx_app_config
#
# file =open('default.conf',mode='w')
# file.write(nginx_str%nginx_app_str)
# file.close()
# compose_file.close()


# 生成info文件
all_info=[]
for app_name in os.listdir("."):
    if os.path.isdir(app_name):
        if app_name in ['__pycache__','deploy','app1']:
            continue

        if not os.path.exists(os.path.join(app_name, 'info.json')):
            continue

        info = json.load(open(os.path.join(app_name,'info.json')))
        if 'pic' in info and 'http' not in info['pic']:
            if env=='dev':
                info['pic']=f"http://star.tme.woa.com/{app_name}/static/example/"+app_name+"/" + info['pic']
            else:
                info['pic'] = f"http://www.data-master.net:8888/{app_name}/static/example/" + app_name + "/" + info['pic']
        app_name = app_name.lower().replace('_', '-')
        info['doc'] = f"http://www.data-master.net:8888/aihub/{app_name}" if env=='cloud' else f"http://star.tme.woa.com/aihub/{app_name}"
        all_info.append(info)

file = open('info.json',mode='w')
file.write(json.dumps(all_info,indent=2,ensure_ascii=False))
file.close()

