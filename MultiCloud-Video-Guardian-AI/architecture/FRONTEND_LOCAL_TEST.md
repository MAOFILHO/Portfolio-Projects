# Frontend Local Testing Guide

Quick guide to test the frontend locally before deploying to AKS.

---

## Quick Start (10 minutes)

### Step 1: Install Dependencies
```bash
cd frontend
npm install
```

### Step 2: Start Development Server
```bash
# Start frontend (opens at http://localhost:3000)
npm start
```

### Step 3: Start Backend Services
```bash
# In another terminal, start backend services
cd ..
docker-compose up -d

# Verify services are running
curl http://localhost:8000/health  # Ingestion
curl http://localhost:8004/health  # Human Review
curl http://localhost:8006/health  # API Gateway
```

### Step 4: Test in Browser
```bash
# Open browser
open http://localhost:3000

# You should see:
# - Navigation bar with "Upload", "Dashboard", "Review Queue"
# - Upload page with drag & drop zone
```

---

## Testing Each Page

### Upload Page
1. Navigate to http://localhost:3000/upload
2. Drag a test video file (MP4, MOV, or AVI)
3. Click upload
4. Should see progress bar
5. Should see success message with job ID
6. Click "View Dashboard"

### Dashboard Page
1. Navigate to http://localhost:3000/dashboard
2. Should see statistics cards (total, approved, rejected, etc.)
3. Should see video grid with uploaded videos
4. Try searching by filename
5. Try filtering by status tabs
6. Click "View Details" on a video

### Review Queue Page
1. Navigate to http://localhost:3000/review
2. Should see videos pending review (if any)
3. Click "Review" button on a video
4. Dialog opens with scores
5. Add notes and click "Approve" or "Reject"
6. Video removed from queue

### Video Details Page
1. Click on any video card from dashboard
2. Should see video player (if streaming configured)
3. Should see all metadata and scores
4. Should see processing timeline
5. Should see review notes (if reviewed)

---

## Troubleshooting

### Frontend won't start
```bash
# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm install
npm start
```

### API calls fail (CORS errors)
```bash
# Check backend services are running
docker-compose ps

# Check API Gateway has CORS enabled
curl http://localhost:8006/health
```

### Videos don't appear in dashboard
```bash
# Check DynamoDB has data
aws dynamodb scan --table-name guardian-videos --limit 5

# Check API Gateway can query DynamoDB
curl http://localhost:8006/videos | jq .
```

### Upload fails
```bash
# Check ingestion service logs
docker-compose logs ingestion

# Test ingestion directly
curl -X POST http://localhost:8000/upload -F "file=@test.mp4"
```

---

## Build for Production

### Build Static Files
```bash
cd frontend
npm run build

# Output in build/ directory
ls -la build/
```

### Test Production Build Locally
```bash
# Install serve
npm install -g serve

# Serve production build
serve -s build -p 3000

# Test
open http://localhost:3000
```

### Build Docker Image
```bash
cd ..
docker build -t guardian-ai-frontend:local ./frontend

# Run container
docker run -p 3000:80 guardian-ai-frontend:local

# Test
open http://localhost:3000
```

---

## Success Checklist

- [ ] npm install successful
- [ ] npm start opens browser at localhost:3000
- [ ] Upload page loads without errors
- [ ] Dashboard page loads without errors
- [ ] Review Queue page loads without errors
- [ ] Navigation between pages works
- [ ] Can upload a video via UI
- [ ] Video appears in dashboard
- [ ] Can view video details
- [ ] Can submit review (if video in queue)
- [ ] No console errors in browser
- [ ] Production build successful (npm run build)
- [ ] Docker image builds successfully

---

**Time**: 10-15 minutes
**Status**: ✅ Ready for local testing

🚀 **Test the frontend before deploying to AKS!**
