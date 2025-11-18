# Dify Kubernetes Deployment

OrbStack K3s 환경에서 Dify를 배포하기 위한 Kustomize 기반 Kubernetes manifests입니다.

## 디렉토리 구조

```
k8s/
├── base/                    # Kustomize base 설정
│   ├── kustomization.yaml
│   ├── namespace.yaml
│   ├── pv-hostpath.yaml     # RWX용 hostPath PV
│   ├── configmap-env.yaml   # 환경 변수
│   ├── configmap-nginx.yaml # nginx 설정
│   ├── secrets.env.example  # Secrets 템플릿 (Git 추적)
│   ├── secrets.env          # 실제 Secrets (gitignore 처리)
│   ├── postgresql/          # PostgreSQL StatefulSet
│   ├── redis/               # Redis StatefulSet
│   ├── api/                 # API Deployment
│   ├── worker/              # Worker Deployment
│   ├── worker-beat/         # Worker Beat Deployment
│   ├── web/                 # Web Deployment
│   └── nginx/               # Nginx Deployment (NodePort)
└── overlays/
    ├── development/         # Development 환경 설정
    └── production/          # Production 환경 설정
```

## 주요 구성 요소

### 스토리지 전략
- **RWO (ReadWriteOnce)**: `local-path` StorageClass 사용
  - PostgreSQL: 10Gi
  - Redis: 5Gi
- **RWX (ReadWriteMany)**: `hostPath` PersistentVolume 사용
  - App Storage: 50Gi (api, worker, worker-beat 공유)

### 서비스 구성
- **PostgreSQL**: StatefulSet (1 replica)
- **Redis**: StatefulSet (1 replica)
- **API**: Deployment (2 replicas)
- **Worker**: Deployment (2 replicas)
- **Worker Beat**: Deployment (1 replica)
- **Web**: Deployment (2 replicas)
- **Nginx**: Deployment (1 replica), NodePort 30080

### 외부 접근
- **NodePort**: `http://localhost:30080`
- OrbStack K3s의 단일 노드 환경에서 동작

## 배포 방법

### 1. Secrets 설정

템플릿에서 secrets 파일을 생성하고 값을 수정하세요:

```bash
# secrets.env 파일 생성
cp k8s/base/secrets.env.example k8s/base/secrets.env

# 에디터로 열어서 프로덕션 값으로 변경
vim k8s/base/secrets.env
```

**중요**: 프로덕션 환경에서는 다음 값들을 반드시 새로 생성하세요:
```bash
# SECRET_KEY 생성
openssl rand -base64 42

# ENCRYPT_PUBLIC_KEY 생성
openssl rand -base64 42

# PLUGIN_DAEMON_KEY 생성
openssl rand -base64 42

# PLUGIN_DIFY_INNER_API_KEY 생성
openssl rand -base64 42
```

### 2. Base 배포

```bash
# Dry-run으로 생성될 리소스 확인
kubectl kustomize k8s/base/

# 배포
kubectl apply -k k8s/base/
```

### 3. Development Overlay 배포

```bash
# Development 환경 배포 (replicas=1, DEBUG=true)
kubectl apply -k k8s/overlays/development/
```

### 4. Production Overlay 배포

```bash
# Production 환경 배포 (replicas=3, DEBUG=false)
kubectl apply -k k8s/overlays/production/
```

## 배포 확인

```bash
# Namespace 확인
kubectl get ns dify

# Pod 상태 확인
kubectl get pods -n dify

# Service 확인
kubectl get svc -n dify

# PVC 확인
kubectl get pvc -n dify

# PV 확인
kubectl get pv
```

## 접속

```bash
# NodePort로 접근
open http://localhost:30080
```

## 로그 확인

```bash
# API Pod 로그
kubectl logs -n dify -l app.kubernetes.io/component=api -f

# Worker Pod 로그
kubectl logs -n dify -l app.kubernetes.io/component=worker -f

# Web Pod 로그
kubectl logs -n dify -l app.kubernetes.io/component=web -f
```

## 삭제

```bash
# Base 배포 삭제
kubectl delete -k k8s/base/

# 또는 Development overlay 삭제
kubectl delete -k k8s/overlays/development/

# PV 수동 삭제 (데이터 유지 정책 때문에 자동 삭제되지 않음)
kubectl delete pv dify-app-storage-pv
```

## 주의사항

### 1. hostPath 스토리지
- `dify-app-storage` PV는 hostPath를 사용하여 `/var/lib/dify/storage`에 데이터 저장
- OrbStack의 단일 노드 환경에서만 동작
- 모든 Pod는 `orbstack` 노드에 스케줄링됨 (nodeAffinity 설정)

### 2. Secrets 관리
- Kustomize `secretGenerator`를 사용하여 `secrets.env`에서 Secret 생성
- `secrets.env`는 `.gitignore`로 제외됨 (민감정보 보호)
- `secrets.env.example`은 Git에 포함되어 새로운 환경에서 쉽게 시작 가능
- 프로덕션 환경에서는 External Secrets Operator 사용도 고려

### 3. 초기 설정
- API Pod의 initContainer가 자동으로 DB 마이그레이션 실행
- 첫 배포 시 PostgreSQL과 Redis가 먼저 Ready 상태가 되어야 함

### 4. 리소스 제한
- Development: 최소 리소스 (replicas=1)
- Production: 권장 리소스 (replicas=2-3)
- 필요에 따라 `resources.requests/limits` 조정

## 트러블슈팅

### Pod가 Pending 상태일 때
```bash
# PVC 바인딩 확인
kubectl get pvc -n dify

# PV 상태 확인
kubectl get pv

# Pod describe로 이벤트 확인
kubectl describe pod -n dify <pod-name>
```

### DB 연결 오류
```bash
# PostgreSQL Pod 상태 확인
kubectl get pod -n dify -l app.kubernetes.io/component=postgresql

# PostgreSQL 로그 확인
kubectl logs -n dify -l app.kubernetes.io/component=postgresql

# DB 마이그레이션 확인 (API initContainer 로그)
kubectl logs -n dify -l app.kubernetes.io/component=api -c db-migrate
```

### hostPath 볼륨 권한 문제
```bash
# OrbStack 노드에 접속하여 디렉토리 권한 확인
docker exec -it orbstack sh
ls -la /var/lib/dify/storage
chmod -R 777 /var/lib/dify/storage
```

## 환경 변수 커스터마이징

`k8s/base/configmap-env.yaml`을 수정하거나, overlay에서 `configMapGenerator`를 사용하세요:

```yaml
# overlays/development/kustomization.yaml
configMapGenerator:
  - name: dify-env
    behavior: merge
    literals:
      - LOG_LEVEL=DEBUG
      - CUSTOM_VAR=value
```

## 참고사항

- Docker Compose에서 제외된 컴포넌트: A2A Gateway, Sandbox, Plugin Daemon, Vector DB
- A2A Gateway는 별도 저장소(`~/Git/a2a-edge`)에서 관리
- Vector DB(Weaviate/Qdrant) 추가가 필요한 경우 별도 manifest 작성 필요
