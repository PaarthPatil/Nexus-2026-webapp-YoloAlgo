# Nexus Startup Guide

Follow these steps to run the complete Nexus system.

## 1. Prerequisites
- **Python 3.10+** (Recommended)
- **Node.js 16+**

## 2. Start Backend
In a new terminal window:
```powershell
# Navigate to backend
cd nexustrace/backend

# Install dependencies if not done
pip install -r requirements.txt

# Start the server
python main.py
```
> [!NOTE]
> The backend will listen on `http://127.0.0.1:8000`. 
> All authentication is currently DISABLED for easy administrative access.

## 3. Start Frontend
In another terminal window:
```powershell
# Navigate to frontend
cd nexustrace/frontend

# Install dependencies if not done
npm install

# Start development server
npm run dev
```
> [!NOTE]
> The frontend will typically listen on `http://localhost:5173`.

---

## High-Accuracy Detection (Nexus Optimized)
To use the most accurate object detection mode:
1. Open the **Dashboard**.
2. Expand **Advanced Engine Params**.
3. In the **Algorithm** dropdown, select **Nexus Optimized (Accurate)**.
4. Set **Source Location** (e.g., `boxvid.mp4` or a file path).
5. Press **EXECUTE SEQUENCE**.

### Standalone Testing
If you want to run the detection script independently:
```powershell
# In the project root
python run_yolo_nexus_optimized.py
```
