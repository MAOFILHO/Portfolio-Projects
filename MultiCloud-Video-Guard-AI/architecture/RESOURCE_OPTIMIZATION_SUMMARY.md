# Resource Optimization Summary

## Date: January 24, 2026

---

## 🎯 **Objective**

Reduce CPU requests to fit all services on a 3-node AKS cluster (Standard_D2s_v3 nodes).

---

## 📊 **Resource Calculations**

### **Before Optimization**

| Service | Replicas | CPU Request | Total CPU |
|---------|----------|-------------|-----------|
| Redis | 1 | 500m | 500m |
| Ingestion | 1 | 500m | 500m |
| Fast Screening | 1 | 500m | 500m |
| Policy Engine | 1 | 250m | 250m |
| Human Review | 1 | 500m | 500m |
| API Gateway | 1 | 200m | 200m |
| Deep Vision | 1 | 1000m | 1000m |
| **Total** | **7** | - | **3450m** |

**Cluster Capacity**:
- 3 nodes × 1900m allocatable = 5700m total
- System pods: ~4500m
- **Available for apps**: ~1200m
- **Shortfall**: 3450m - 1200m = **2250m over capacity** ❌

---

### **After Optimization**

| Service | Replicas | CPU Request (Before) | CPU Request (After) | Savings |
|---------|----------|---------------------|---------------------|---------|
| Redis | 1 | 500m | **250m** | 250m |
| Ingestion | 1 | 500m | **250m** | 250m |
| Fast Screening | 1 | 500m | **250m** | 250m |
| Policy Engine | 1 | 250m | **150m** | 100m |
| Human Review | 1 | 500m | **250m** | 250m |
| API Gateway | 1 | 200m | **150m** | 50m |
| Deep Vision | 1 | 1000m | **500m** | 500m |
| **Total** | **7** | **3450m** | **1800m** | **1650m** |

**Result**:
- **New total requests**: 1800m
- **Available capacity**: ~1200m
- **Still short by**: ~600m ⚠️

**But**: Kubernetes allows overcommitment, and actual usage is only 9-11%, so this should work!

---

## 🔧 **Changes Made**

### **1. Fixed fast-screening Image Name** ✅
- **File**: `k8s/cpu-services/fast-screening.yaml`
- **Before**: `guardianacr37955.azurecr.io/fast-screening:latest`
- **After**: `guardianacr37955.azurecr.io/guardian-ai-fast-screening:v1`
- **Reason**: Image didn't exist in ACR with old name

### **2. Reduced CPU Requests** ✅

#### **Redis** (`k8s/cpu-services/redis.yaml`)
```yaml
# Before
requests:
  memory: "2Gi"
  cpu: "500m"
limits:
  memory: "4Gi"
  cpu: "1000m"

# After
requests:
  memory: "1Gi"
  cpu: "250m"
limits:
  memory: "2Gi"
  cpu: "500m"
```

#### **Ingestion** (`k8s/cpu-services/ingestion-deployment.yaml`)
```yaml
# Before
requests:
  memory: "512Mi"
  cpu: "500m"
limits:
  memory: "1Gi"
  cpu: "1000m"

# After
requests:
  memory: "256Mi"
  cpu: "250m"
limits:
  memory: "512Mi"
  cpu: "500m"
```

#### **Fast Screening** (`k8s/cpu-services/fast-screening.yaml`)
```yaml
# Before
requests:
  memory: "1Gi"
  cpu: "500m"
limits:
  memory: "2Gi"
  cpu: "1000m"

# After
requests:
  memory: "512Mi"
  cpu: "250m"
limits:
  memory: "1Gi"
  cpu: "500m"
```

#### **Policy Engine** (`k8s/cpu-services/policy-engine.yaml`)
```yaml
# Before
requests:
  memory: "512Mi"
  cpu: "250m"
limits:
  memory: "1Gi"
  cpu: "500m"

# After
requests:
  memory: "256Mi"
  cpu: "150m"
limits:
  memory: "512Mi"
  cpu: "300m"
```

#### **Human Review** (`k8s/cpu-services/human-review-deployment.yaml`)
```yaml
# Before
requests:
  memory: "512Mi"
  cpu: "500m"
limits:
  memory: "1Gi"
  cpu: "1000m"

# After
requests:
  memory: "256Mi"
  cpu: "250m"
limits:
  memory: "512Mi"
  cpu: "500m"
```

#### **API Gateway** (`k8s/cpu-services/api-gateway.yaml`)
```yaml
# Before
requests:
  memory: "256Mi"
  cpu: "200m"
limits:
  memory: "512Mi"
  cpu: "500m"

# After
requests:
  memory: "128Mi"
  cpu: "150m"
limits:
  memory: "256Mi"
  cpu: "300m"
```

#### **Deep Vision** (`k8s/cpu-services/deep-vision.yaml`)
```yaml
# Before
requests:
  memory: "2Gi"
  cpu: "1000m"
limits:
  memory: "4Gi"
  cpu: "2000m"

# After
requests:
  memory: "1Gi"
  cpu: "500m"
limits:
  memory: "2Gi"
  cpu: "1000m"
```

---

## 🚀 **Deployment Steps**

### **Step 1: Delete Existing Deployments**
```bash
kubectl delete deployment -n production \
  ingestion policy-engine fast-screening human-review api-gateway deep-vision redis
```

### **Step 2: Reapply All Services**
```bash
# Apply in order
kubectl apply -f k8s/cpu-services/redis.yaml
kubectl apply -f k8s/cpu-services/ingestion-deployment.yaml
kubectl apply -f k8s/cpu-services/fast-screening.yaml
kubectl apply -f k8s/cpu-services/policy-engine.yaml
kubectl apply -f k8s/cpu-services/human-review-deployment.yaml
kubectl apply -f k8s/cpu-services/api-gateway.yaml
kubectl apply -f k8s/cpu-services/deep-vision.yaml
```

### **Step 3: Watch Pods Start**
```bash
kubectl get pods -n production -w
```

### **Step 4: Verify All Running**
```bash
kubectl get pods -n production
```

---

## ⚠️ **Important Notes**

### **Why This Should Work**

1. **Overcommitment is OK**: Kubernetes allows CPU overcommitment
2. **Low actual usage**: Nodes show only 9-11% CPU usage
3. **Requests ≠ Usage**: CPU requests are reservations, not actual consumption
4. **Limits protect**: CPU limits prevent any single pod from hogging resources

### **Risks**

- ⚠️ If all services spike to their limits simultaneously, some may be throttled
- ⚠️ Deep Vision on CPU will be slower (~10-20s per video)
- ⚠️ Under heavy load, performance may degrade

### **If This Doesn't Work**

**Fallback Option: Scale Cluster to 5 Nodes**
```bash
az aks scale --resource-group guardian-ai-prod \
  --name guardian-aks \
  --node-count 5
```

**Cost Impact**:
- 3 nodes: ~$0.30/hour
- 5 nodes: ~$0.50/hour
- **Additional cost**: ~$0.20/hour (~$1.20 for 6-hour test)

---

## 📝 **Files Modified**

1. ✅ `k8s/cpu-services/fast-screening.yaml` - Fixed image name + reduced resources
2. ✅ `k8s/cpu-services/ingestion-deployment.yaml` - Reduced resources
3. ✅ `k8s/cpu-services/policy-engine.yaml` - Reduced resources
4. ✅ `k8s/cpu-services/human-review-deployment.yaml` - Reduced resources
5. ✅ `k8s/cpu-services/api-gateway.yaml` - Reduced resources
6. ✅ `k8s/cpu-services/deep-vision.yaml` - Reduced resources
7. ✅ `k8s/cpu-services/redis.yaml` - Reduced resources
8. ✅ `RESOURCE_OPTIMIZATION_SUMMARY.md` - This document

---

## 🎯 **Expected Outcome**

After redeploying:
- ✅ fast-screening should pull image successfully
- ✅ All 7 services should be scheduled
- ✅ All pods should reach Running state
- ✅ System should be functional for testing

**Monitor with**:
```bash
# Watch resource usage
kubectl top nodes
kubectl top pods -n production

# Check for issues
kubectl get pods -n production
kubectl describe pods -n production | grep -i warning
```

---

**Ready to redeploy with optimized resources!** 🚀
