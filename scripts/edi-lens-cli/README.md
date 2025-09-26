# EDI Lens CLI - Interactive NiFi Flow Manager

A powerful command-line interface for managing Apache NiFi flows, Registry operations, and version control.

## 🚀 Features

- **📁 Flow Management**: Deploy, start, stop, and delete NiFi flows
- **📋 Registry Operations**: Manage buckets, flows, and versions
- **🔀 Version Control**: Commit, update, and revert flow changes
- **🏥 System Health**: Monitor NiFi, Registry, and backend services
- **⚙️ Settings**: Configure CLI behavior and endpoints

## 📋 Prerequisites

- Python 3.8+
- Running EDI Lens backend (port 8000)
- Apache NiFi (port 8443)
- NiFi Registry (port 18080)

## 🛠️ Installation

1. **Install dependencies**:
   ```bash
   pip install httpx
   ```

2. **Make the CLI executable**:
   ```bash
   chmod +x scripts/edi-lens-cli/main.py
   ```

## 🎯 Usage

### Quick Start
```bash
# Run the CLI
cd edi-lens
python scripts/edi-lens-cli/main.py
```

### Environment Configuration
The CLI automatically detects your environment configuration from:
- `.env.local` (for local development)
- `.env.docker` (for Docker environment)
- Environment variables

### Flow Templates
Place your flow template JSON files in the `data/flows/` directory:
```
data/
├── flows/
│   ├── simple-file-processing.json
│   ├── edi-parsing-flow.json
│   └── custom/
│       └── my-custom-flow.json
└── test-data/
    └── sample-files/
```

## 📖 Flow Template Format

Flow templates are JSON files that define NiFi flows with parameter placeholders:

```json
{
  "name": "My Flow",
  "description": "Description of the flow",
  "processors": [
    {
      "identifier": "proc-001",
      "name": "GetFile",
      "type": "org.apache.nifi.processors.standard.GetFile",
      "properties": {
        "Input Directory": "#{input_directory}",
        "File Filter": "#{file_pattern}"
      }
    }
  ],
  "connections": [
    {
      "source": {"id": "proc-001", "type": "PROCESSOR"},
      "destination": {"id": "proc-002", "type": "PROCESSOR"},
      "selectedRelationships": ["success"]
    }
  ]
}
```

### Parameter Placeholders
Use `#{parameter_name}` syntax in flow templates. The CLI will automatically detect these and prompt for values during deployment.

## 🎮 Interactive Menus

### Main Menu
- **📁 Flow Management**: Deploy and manage flows
- **📋 Registry Operations**: Browse buckets and flows
- **🔀 Version Control**: Commit/update flows
- **🏥 System Health**: Monitor service status
- **⚙️ Settings**: Configure CLI behavior

### Flow Management
- Deploy new flows from templates
- Import existing flows from Registry
- Start/stop flows
- Delete flows
- View flow status

### Registry Operations
- List buckets and flows
- View flow details and versions
- Browse Registry contents

### Version Control
- Commit local changes to Registry
- Update flows from Registry
- Revert local modifications
- Check for differences

## 🏥 Health Monitoring

The CLI provides comprehensive health monitoring:
- Backend API connectivity
- NiFi service status
- Registry service status
- Detailed connectivity tests

## ⚙️ Configuration

### Backend URL
Default: `http://localhost:8000`

Change via Settings menu or environment variable:
```bash
export EDI_LENS_BACKEND_URL=http://your-backend:8000
```

### Data Directories
- **Flows**: `data/flows/` - Flow template files
- **Test Data**: `data/test-data/` - Sample files for testing

## 🔧 Development

### Project Structure
```
scripts/edi-lens-cli/
├── main.py              # Entry point
├── cli_app.py           # Main application class
├── api/
│   └── client.py        # Backend API client
├── menus/
│   ├── base_menu.py     # Base menu class
│   ├── main_menu.py     # Main menu
│   ├── flow_menu.py     # Flow management
│   ├── registry_menu.py # Registry operations
│   ├── version_control_menu.py
│   ├── health_menu.py   # System health
│   └── settings_menu.py # Configuration
└── utils/
    ├── config.py        # Configuration management
    ├── display.py       # Terminal output formatting
    └── logger.py        # Logging setup
```

### Adding New Features

1. **New Menu**: Extend `BaseMenu` class
2. **New API Endpoint**: Add method to `EDILensAPIClient`
3. **New Flow Template**: Add JSON file to `data/flows/`

## 🐛 Troubleshooting

### Common Issues

**Connection Refused**
- Ensure backend is running on port 8000
- Check NiFi is accessible on port 8443
- Verify Registry is running on port 18080

**Invalid Flow Template**
- Validate JSON syntax
- Ensure required fields (name, processors) are present
- Check processor types are valid NiFi processor classes

**Authentication Errors**
- Verify NiFi credentials in environment configuration
- Check SSL certificate settings

### Debug Mode
Enable debug logging:
```bash
export EDI_LENS_DEBUG=true
python scripts/edi-lens-cli/main.py
```

### Logs
Check logs in `logs/edi-lens-cli-YYYYMMDD.log`

## 📚 API Reference

The CLI uses the EDI Lens backend API. Available endpoints:

- `GET /health` - System health
- `POST /api/flows/deploy-and-store` - Deploy flow
- `GET /api/flows/{id}/status` - Flow status
- `POST /api/flows/{id}/start` - Start flow
- `POST /api/flows/{id}/stop` - Stop flow
- `DELETE /api/flows/{id}` - Delete flow
- `GET /api/flows/registry/buckets` - List buckets
- And more...

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

Copyright © 2024 EDI Lens Team. All rights reserved.