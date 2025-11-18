# Dify Kubernetes 배포 가이드

OrbStack 또는 다른 Kubernetes 환경에서 Dify를 배포하는 가이드입니다.

## 사전 요구사항

- Kubernetes 클러스터 (OrbStack, minikube, kind 등)
- kubectl CLI
- kustomize (kubectl 1.14+ 포함)

## 빠른 시작

```bash
# Development 환경 배포
cd k8s/overlays/development
kustomize build . --enable-helm | kubectl apply -f -

# 파드 상태 확인
kubectl get pods -n dify

# 서비스 접속 (OrbStack)
open http://localhost:30080
```

## 로컬 이미지 빌드 (이미지 pull 실패 시)

네트워크 문제로 이미지 pull이 실패하는 경우:

```bash
# 1. API 이미지 빌드
cd /path/to/dify/api
docker build -t langgenius/dify-api:1.9.2 .

# 2. Web 이미지 빌드
cd ../web
docker build -t langgenius/dify-web:1.9.2 .

# 3. 기타 이미지는 Docker Compose로 pull
cd ../docker
docker compose pull postgres redis nginx sandbox plugin_daemon ssrf_proxy

# 4. K8s 파드 재시작
kubectl delete pods --all -n dify
```

## 주요 기능

### 자동 구성
- ✅ **PostgreSQL**: `dify`, `dify_plugin` 데이터베이스 자동 생성
- ✅ **SSRF Proxy**: marketplace.dify.ai 접근 허용
- ✅ **Plugin Daemon**: 플러그인 관리 시스템 활성화

### 서비스 엔드포인트
- **Nginx** (외부): `localhost:30080` (NodePort)
- **API**: `api:5001` (ClusterIP)
- **Web**: `web:3000` (ClusterIP)
- **PostgreSQL**: `postgresql:5432` (ClusterIP)
- **Redis**: `redis:6379` (ClusterIP)

## 문제 해결

### 1. ImagePullBackOff

**증상**: 모든 파드가 이미지를 pull하지 못함

**해결**:
```bash
# OrbStack 재시작
orb stop && orb start

# 또는 로컬 빌드 (위 참조)
```

### 2. Plugin Daemon CrashLoopBackOff

**증상**: `database "dify_plugin" does not exist`

**해결**:
- 자동 해결됨 (PostgreSQL init script 포함)
- 수동: `kubectl exec -n dify postgresql-0 -- psql -U postgres -c "CREATE DATABASE dify_plugin;"`

### 3. Marketplace 403 오류

**증상**: 플러그인 다운로드 시 `403 Forbidden`

**해결**: 자동 해결됨 (SSRF proxy localnet 허용)

### 4. "plugin not found" 오류

**증상**: 앱 설정에서 플러그인 오류

**해결**:
1. Console → Apps → Settings → Plugins
2. 먼저 플러그인 추가
3. 그 다음 Model Config 설정

## 호스트 머신 접속

K8s 파드에서 호스트(맥)의 서비스 접근:

```bash
# 예: 맥에서 실행 중인 Ollama
ollama_url="http://host.docker.internal:11434"

# 테스트
kubectl exec -n dify deploy/api -- curl http://host.docker.internal:11434
```

## 환경별 배포

### Development (기본)
```bash
cd k8s/overlays/development
kustomize build . --enable-helm | kubectl apply -f -
```
- 디버그 로그 활성화
- 최소 리소스

### Production
```bash
cd k8s/overlays/production
kustomize build . --enable-helm | kubectl apply -f -
```
- 프로덕션 로그 레벨
- 높은 리소스 할당

## 데이터 영속성

PersistentVolume 위치 (OrbStack):
- **App Storage**: `/var/lib/dify/app-storage`
- **Plugin Storage**: `/var/lib/dify/plugin-storage`
- **Sandbox**: `/var/lib/dify/sandbox-dependencies`
- **PostgreSQL/Redis**: Dynamic provisioning

## 완전 제거

```bash
# 리소스 삭제
cd k8s/overlays/development
kubectl delete -f <(kustomize build . --enable-helm)

# PV도 제거 (데이터 손실!)
kubectl delete pv --all
```

## 디렉토리 구조

```
k8s/
├── base/                           # 기본 리소스
│   ├── postgresql/
│   │   ├── init-configmap.yaml    # DB 자동 생성
│   │   ├── statefulset.yaml
│   │   └── service.yaml
│   ├── ssrf-proxy/
│   │   └── configmap.yaml          # marketplace 허용
│   ├── api/, web/, worker/...
│   └── kustomization.yaml
├── overlays/
│   ├── development/                # 개발 환경
│   └── production/                 # 프로덕션 환경
└── SETUP.md                        # 이 문서
```

## 다른 팀원에게 전달

이 디렉토리를 공유하면 바로 배포 가능합니다:

```bash
# 1. 저장소 클론 또는 k8s/ 디렉토리 복사
git clone <repo-url>
cd dify/k8s/overlays/development

# 2. 배포
kustomize build . --enable-helm | kubectl apply -f -

# 3. 대기 (1-2분)
kubectl get pods -n dify -w

# 4. 접속
open http://localhost:30080
```

**모든 설정이 자동으로 적용됩니다:**
- ✅ dify_plugin DB 생성
- ✅ SSRF proxy 설정
- ✅ 모든 서비스 연결

DB export/import 필요 없음!
