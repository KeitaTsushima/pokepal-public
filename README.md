# PokePal – Open‑Source Conversational AI Framework

**Version**: v0.0.88 | **Architecture**: Clean Architecture v2 Complete | **Initial Use Case**: Elderly Care

An open AI conversation framework running on edge devices with centralized management for multi-device deployment.
Built with Azure IoT Edge for privacy-focused edge processing and automatic updates.
Designing natural interactions in shared living spaces, starting with elderly care facilities.

## ✨ Features

- 💬 **Multi-Modal Interaction**: AI-powered conversational interface (voice, text, visual) adaptable to various contexts
- 🔒 **Privacy-First**: Edge-based processing architecture for sensitive data handling
- 🔄 **Automatic Updates**: Remote updates via Azure IoT Edge
- 📊 **Centralized Management**: Monitor and control multiple devices from central dashboard
- 🎯 **Customizable Applications**: Medication reminders, conversation analytics, and more

## 🛠 Tech Stack

- **Language**: Python 3.11
- **Edge Platform**: Azure IoT Edge
- **Speech Recognition**: OpenAI Whisper API
- **Conversational AI**: OpenAI GPT-4o-mini
- **Text-to-Speech**: OpenAI TTS
- **Containerization**: Docker (ARM64 support)
- **CI/CD**: Azure DevOps Pipeline
- **Architecture**: Clean Architecture

## 📋 Requirements

### Hardware Requirements
- Raspberry Pi 5 (8GB RAM) - Currently supported
- NVIDIA Jetson Orin Nano - Planned support (August 2025)
- USB Microphone & Speakers
- 32GB+ Storage

### Software Requirements
- Ubuntu 22.04 LTS or Raspberry Pi OS (64-bit)
- Docker 20.10+
- Azure IoT Edge 1.4+

## 🚀 Setup

### Quick Start

1. **Clone Repository**
   ```bash
   git clone https://github.com/your-username/PokePal.git
   cd PokePal
   ```

2. **Required Resources**
   - Azure IoT Hub
   - Raspberry Pi 5 (8GB RAM) - see Hardware Requirements for upcoming platform support
   - USB Microphone & Speakers

3. **Deployment**
   - Create Azure resources using ARM Templates
   - Deploy to edge devices via Azure IoT Edge

## 🏗 Architecture

> **Privacy-First Design**: Conversation processing happens on edge devices, while management data is securely synced to Azure for centralized control.

```
┌─────────────────┐     ┌─────────────────┐
│   Edge Device   │     │  Azure Cloud    │
│  (Local AI)     │     │ (Management)    │
│ ┌─────────────┐ │     │ ┌─────────────┐ │
│ │Voice Module │ │◄────┤ │  IoT Hub    │ │
│ └─────────────┘ │     │ └─────────────┘ │
│ ┌─────────────┐ │     │ ┌─────────────┐ │
│ │ Memory Mgr  │ │     │ │ Cosmos DB   │ │
│ └─────────────┘ │     │ └─────────────┘ │
└─────────────────┘     └─────────────────┘
```

## 📁 Project Structure

```
PokePal/
├── EdgeSolution/                    # Azure IoT Edge Solution
│   ├── modules/
│   │   ├── voice_conversation_v2/   # Main voice conversation module
│   │   │   ├── domain/             # Domain layer (business logic)
│   │   │   ├── application/        # Application layer (use cases)
│   │   │   ├── adapters/           # Adapter layer (external interfaces)
│   │   │   │   ├── input/          # Input adapters (IoT, signals)
│   │   │   │   └── output/         # Output adapters (audio, telemetry)
│   │   │   ├── infrastructure/     # Infrastructure layer (external dependencies)
│   │   │   │   ├── ai/             # AI services (Whisper, GPT, TTS)
│   │   │   │   ├── audio/          # Audio processing (VAD, devices)
│   │   │   │   ├── config/         # Configuration management
│   │   │   │   ├── memory/         # Memory management
│   │   │   │   └── security/       # Security services
│   │   │   ├── tests/              # Unit, integration & E2E tests
│   │   │   └── main.py             # Entry point
│   │   ├── system-monitor/         # System monitoring module
│   │   └── base-image/             # Shared base image
│   └── deployment.template.json    # Edge deployment configuration
├── azure-functions/                # Azure Functions (cloud processing)
│   ├── ConversationLogger/         # Conversation log storage
│   └── MemoryGenerator/            # Memory file generation
├── azure-initial-setup/            # Azure initial setup
│   └── arm-templates/              # ARM Template collection
├── docs/                           # Project documentation
├── tests/                          # E2E & integration tests
│   ├── integration/                # Integration tests
│   ├── experimental/               # Experimental tests
│   └── e2e/                        # End-to-End tests
├── scripts/                        # Development support scripts
└── azure-pipelines.yml            # CI/CD pipeline
```

## 🤝 Contributing

This project is published as open source.
Feel free to submit feedback and suggestions via Issues.

## 📄 License

MIT License - See [LICENSE](LICENSE) for details.

## 👥 Development Team

- Project Owner: Keita Tsushima

## 🎯 Development Status

### Completed Features
- ✅ Clean Architecture implementation complete (v2)
- ✅ Voice conversation system (Whisper + GPT-4o-mini + TTS)
- ✅ IoT Hub integration & remote control
- ✅ Memory system & conversation history management
- ✅ Proactive features (medication reminders, etc.)
- ✅ Automated testing environment

### In Development
- 🔄 TTS audio quality optimization
- 🔄 Whisper model lightweight evaluation

### 🚀 Future Roadmap

**Early August 2025**: Code quality assurance and optimization. Open source release preparation

**Late August 2025**: Multi-device deployment with NVIDIA Jetson platform. Device design consultation for physical form factor

**September 2025**: Web-based admin dashboard development using Vue.js. Mobile application development for iOS platform

**October 2025**: Pilot deployment with initial customers. Staff monitoring and control application development

**November 2025**: Interactive robot integration with [Reachy Mini platform](https://huggingface.co/blog/reachy-mini)

**End of Year Goal**: Comprehensive elderly care ecosystem with autonomous conversational devices, centralized monitoring dashboard, and mobile staff applications

## 🎯 Philosophy

We believe that meaningful human-AI interaction should be **accessible, privacy-respecting, and community-driven**. 

By open-sourcing this conversational AI framework, we aim to:
- **Democratize AI interaction technology** - Enable developers and organizations to build their own conversational solutions
- **Preserve privacy by design** - Process conversations on edge devices while maintaining centralized management capabilities  
- **Foster collaborative innovation** - Share architectural patterns and lessons learned from real-world deployment
- **Bridge technology and human connection** - Focus on natural, context-aware interactions that enhance rather than replace human relationships

This project represents our exploration into creating technology that truly serves human needs, starting with elderly care but extending to any environment where natural conversation matters.

## 📧 Contact

For questions or inquiries about this project, please use GitHub Issues.