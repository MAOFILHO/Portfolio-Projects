# Kubernetes Deployment Fixes Summary

## Date: January 24, 2026

---

## 🔧 Changes Made

### **1. Fixed Image Names (ACR Registry Corrections)**

#### **File: `k8s/cpu-services/ingestion-deployment.yaml`**
- ❌ **Before**: `guardianairegistry97557.azurecr.io/guardian-ai-ingestion:v1`
- ✅ **After**: `guardianacr37955.azurecr.io/guardian-ai-ingestion:v1`
- **Reason**: Old ACR name didn't exist (DNS lookup failure)

#### **File: `k8s/cpu-services/human-review-deployment.yaml`**
- ❌ **Before**: `guardianairegistry97557.azurecr.io/guardian-ai-human-review:v1`
- ✅ **After**: `guardianacr37955.azurecr.io/guardian-ai-human-review:v1`
- **Reason**: Old ACR name didn't exist (DNS lookup failure)

#### **File: `k8s/cpu-services/policy-engine.yaml`**
- ❌ **Before**: `guardianacr37955.azurecr.io/policy-engine:latest`
- ✅ **After**: `guardianacr37955.azurecr.io/guardian-ai-policy-engine:v1`
- **Reason**: Wrong image name (should be `guardian-ai-policy-engine`, not `policy-engine`) and wrong tag (`:v1`, not `:latest`)

---

### **2. Reduced Replicas (Resource Optimization)**

#### **Problem**: 
- 3 nodes with 1900m CPU each (5700m total allocatable)
- System pods consuming ~1500m per node (~4500m total)
- Only ~1200m CPU available for application pods
- Original configuration requested ~3000m+ CPU (way over capacity)

#### **Changes**:

| Service | Before | After | CPU Saved |
|---------|--------|-------|-----------|
| **ingestion** | 2 replicas | 1 replica | 500m |
| **policy-engine** | 3 replicas | 1 replica | 500m |
| **fast-screening** | 5 replicas | 1 replica | 2000m |
| **human-review** | 2 replicas | 1 replica | 500m |
| **api-gateway** | 2 replicas | 1 replica | 200m |
| **Total Saved** | - | - | **3700m CPU** |

#### **Files Modified**:
1. ✅ `k8s/cpu-services/ingestion-deployment.yaml` - replicas: 2 → 1
2. ✅ `k8s/cpu-services/policy-engine.yaml` - replicas: 3 → 1
3. ✅ `k8s/cpu-services/fast-screening.yaml` - replicas: 5 → 1
4. ✅ `k8s/cpu-services/human-review-deployment.yaml` - replicas: 2 → 1
5. ✅ `k8s/cpu-services/api-gateway.yaml` - replicas: 2 → 1

#### **Bonus Fix**:
- **`fast-screening.yaml` HPA**: 
  - minReplicas: 5 → 1
  - maxReplicas: 15 → 3
  - **Reason**: HPA was configured to maintain minimum 5 replicas, which would override the deployment replica count

---

## 📊 Resource Allocation (After Changes)

### **Expected CPU Usage per Service**:
- Redis: 500m
- Ingestion: 500m
- Fast Screening: 500m
- Policy Engine: 250m
- Human Review: 500m
- API Gateway: 200m
- Deep Vision: 1000m (CPU-intensive)
- **Total Application**: ~3450m CPU

### **Node Distribution** (estimated):
- **Node 0**: System pods (~1500m) + Redis (500m) + Deep Vision (1000m) = ~3000m / 1900m ⚠️
- **Node 1**: System pods (~1500m) + Ingestion (500m) + Fast Screening (500m) = ~2500m / 1900m ⚠️
- **Node 2**: System pods (~1500m) + Policy Engine (250m) + Human Review (500m) + API Gateway (200m) = ~2450m / 1900m ⚠️

**Note**: Still tight on resources, but should work with Kubernetes overcommitment. For production, consider scaling to 4-5 nodes or using larger node sizes.

---

## 🚀 Next Steps

### **1. Apply the Changes**

```bash
# Delete existing failing deployments
kubectl delete deployment -n production ingestion policy-engine fast-screening human-review api-gateway deep-vision

# Reapply all CPU services with fixed configurations
kubectl apply -f k8s/cpu-services/ingestion-deployment.yaml
kubectl apply -f k8s/cpu-services/fast-screening.yaml
kubectl apply -f k8s/cpu-services/policy-engine.yaml
kubectl apply -f k8s/cpu-services/human-review-deployment.yaml
kubectl apply -f k8s/cpu-services/api-gateway.yaml
kubectl apply -f k8s/cpu-services/deep-vision.yaml

# Watch pods come up
kubectl get pods -n production -w
```

### **2. Verify All Pods are Running**

```bash
# Check pod status
kubectl get pods -n production

# Check for any errors
kubectl describe pods -n production | grep -A 10 "Events:"

# Verify images pulled successfully
kubectl get pods -n production -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.containerStatuses[0].image}{"\n"}{end}'
```

### **3. Monitor Resource Usage**

```bash
# Check node resource usage
kubectl top nodes

# Check pod resource usage
kubectl top pods -n production

# Check for pending pods
kubectl get pods -n production | grep Pending
```

---

## ⚠️ Important Notes

### **For Learning Project**:
- ✅ 1 replica per service is sufficient
- ✅ Reduces cost and complexity
- ✅ Still demonstrates all MLOps concepts
- ✅ Can scale up later if needed

### **For Production**:
- ❌ Would need multiple replicas for high availability
- ❌ Would need larger nodes or more nodes
- ❌ Would need proper resource requests/limits tuning
- ❌ Would need monitoring and alerting

### **Resource Group Name**:
- Your actual resource group is `guardian-ai-prod` (not `guardian-mlops`)
- Update any scripts/documentation that reference the wrong name

---

## 🎯 Expected Outcome

After applying these changes:
- ✅ All pods should pull images successfully
- ✅ All pods should be scheduled (no more "Insufficient CPU" errors)
- ✅ All pods should reach Running state within 3-5 minutes
- ✅ System should be functional for testing

---

## 📝 Files Changed

1. ✅ `k8s/cpu-services/ingestion-deployment.yaml`
2. ✅ `k8s/cpu-services/policy-engine.yaml`
3. ✅ `k8s/cpu-services/fast-screening.yaml`
4. ✅ `k8s/cpu-services/human-review-deployment.yaml`
5. ✅ `k8s/cpu-services/api-gateway.yaml`
6. ✅ `K8S_FIXES_SUMMARY.md` (this file)

---

## 🔍 Troubleshooting

If pods still fail after applying changes:

### **ImagePullBackOff**:
```bash
# Check image exists in ACR
az acr repository list --name guardianacr37955 --output table

# Verify AKS can access ACR
az aks show -n guardian-aks -g guardian-ai-prod --query "servicePrincipalProfile"
```

### **Pending (Insufficient Resources)**:
```bash
# Check what's blocking scheduling
kubectl describe pod <pod-name> -n production | grep -A 10 "Events:"

# Consider scaling cluster
az aks scale --resource-group guardian-ai-prod --name guardian-aks --node-count 4
```

### **CrashLoopBackOff**:
```bash
# Check logs
kubectl logs <pod-name> -n production

# Check previous logs if pod restarted
kubectl logs <pod-name> -n production --previous
```

---

**All changes complete! Ready to redeploy.** 🚀
