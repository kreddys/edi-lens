# 🚀 EDI Lens CLI - Getting Started

Welcome to the EDI Lens CLI! This interactive tool makes managing NiFi flows, Registry operations, and version control easy and intuitive.

## 🎯 Quick Start

### 1. Prerequisites
Make sure you have these services running:
- ✅ EDI Lens Backend (port 8000)
- ✅ Apache NiFi (port 8443) 
- ✅ NiFi Registry (port 18080)

### 2. Install Dependencies
```bash
pip install httpx
```

### 3. Run the CLI
```bash
# From the project root
./scripts/run-cli.sh
```

## 🎮 What You Can Do

### 📁 Flow Management
- **Deploy flows** from JSON templates in `data/flows/`
- **Start/Stop flows** with simple commands
- **Monitor flow status** in real-time
- **Delete flows** when no longer needed

### 📋 Registry Operations  
- **Browse buckets** and flows
- **View flow details** and versions
- **Import flows** from Registry

### 🔀 Version Control
- **Commit changes** to Registry
- **Update flows** from Registry
- **Revert modifications** when needed
- **Check differences** between local and Registry

### 🏥 System Health
- **Monitor services** (Backend, NiFi, Registry)
- **Test connectivity** to all endpoints
- **View system information** and configuration

## 📋 Sample Workflow

1. **Check System Health**
   ```
   Main Menu → System Health → Quick Health Check
   ```

2. **Deploy a Flow**
   ```
   Main Menu → Flow Management → Deploy New Flow
   Select: simple-file-processing
   Configure parameters and deploy
   ```

3. **Monitor the Flow**
   ```
   Flow Management → View Flow Status
   Enter the Process Group ID from deployment
   ```

4. **Make Changes & Commit**
   ```
   (Make changes in NiFi UI)
   Version Control → Commit Changes to Registry
   ```

## 📁 Flow Templates

### Built-in Template
We've included `simple-file-processing.json` that demonstrates:
- **GetFile**: Monitors input directory
- **UpdateAttribute**: Renames files with timestamp
- **PutFile**: Outputs to destination directory

### Creating Custom Templates
1. Place JSON files in `data/flows/`
2. Use parameter placeholders: `#{parameter_name}`
3. Define processors, connections, and properties

### Template Structure
```json
{
  "name": "My Flow",
  "description": "Flow description", 
  "processors": [...],
  "connections": [...],
  "parameters": {
    "input_directory": {
      "description": "Input directory path",
      "default": "/tmp/input"
    }
  }
}
```

## ⚙️ Configuration

### Environment Detection
The CLI automatically detects your environment:
- **Local Development**: Uses `.env.local`
- **Docker Environment**: Uses `.env.docker` 
- **Default**: Fallback configuration

### Backend URL
Change via Settings menu or environment variable:
```bash
export EDI_LENS_BACKEND_URL=http://your-backend:8000
```

## 🔧 Troubleshooting

### Common Issues

**"Connection refused"**
- Ensure backend is running: `./scripts/backend.sh start`
- Check service health: `./scripts/backend.sh health`

**"No flow templates found"**
- Verify files exist in `data/flows/`
- Check JSON syntax is valid

**"Authentication failed"**
- Verify NiFi credentials in environment config
- Check NiFi is accessible at configured URL

### Debug Mode
Enable detailed logging:
```bash
export EDI_LENS_DEBUG=true
./scripts/run-cli.sh
```

## 🎯 Next Steps

1. **Try the sample flow**: Deploy `simple-file-processing.json`
2. **Create test data**: Add files to `data/test-data/`
3. **Build custom flows**: Create your own templates
4. **Explore version control**: Commit and update flows
5. **Monitor health**: Use health checks regularly

## 💡 Tips

- **Use Tab completion**: Many menus support numeric selection
- **Check health first**: Always verify services are running
- **Save Process Group IDs**: You'll need them for flow operations
- **Use meaningful names**: Make flows easy to identify
- **Commit frequently**: Keep Registry up to date

## 🆘 Need Help?

- **Health Menu**: Check system status and connectivity
- **Settings Menu**: View configuration and endpoints  
- **README.md**: Detailed documentation
- **Backend logs**: `./scripts/backend.sh logs`

Happy flow management! 🌊