// DOMIORA Animated AI Assistant Component
class AIAssistantAnimation {
  constructor() {
    this.container = null;
    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.assistant = null;
    this.particles = null;
    this.isSpeaking = false;
    this.init();
  }

  init() {
    // Find AI assistant container
    this.container = document.querySelector('#ai-assistant-3d');
    if (!this.container) return;

    // Scene setup
    this.scene = new THREE.Scene();
    
    // Camera setup
    this.camera = new THREE.PerspectiveCamera(75, this.container.clientWidth / this.container.clientHeight, 0.1, 1000);
    this.camera.position.set(0, 0, 5);
    
    // Renderer setup
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.container.appendChild(this.renderer.domElement);
    
    // Lighting
    this.setupLighting();
    
    // Create AI assistant
    this.createAssistant();
    
    // Create particles
    this.createParticles();
    
    // Event listeners
    this.addEventListeners();
    
    // Start animation
    this.animate();
  }

  setupLighting() {
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
    this.scene.add(ambientLight);
    
    const directionalLight = new THREE.DirectionalLight(0x71212d, 0.8);
    directionalLight.position.set(5, 5, 5);
    this.scene.add(directionalLight);
    
    const pointLight = new THREE.PointLight(0x0b3b5c, 0.5);
    pointLight.position.set(-5, -5, 5);
    this.scene.add(pointLight);
  }

  createAssistant() {
    this.assistant = new THREE.Group();
    
    // Head (sphere)
    const headGeometry = new THREE.SphereGeometry(1, 32, 32);
    const headMaterial = new THREE.MeshStandardMaterial({ 
      color: 0x71212d,
      roughness: 0.3,
      metalness: 0.7,
      emissive: 0x71212d,
      emissiveIntensity: 0.1
    });
    const head = new THREE.Mesh(headGeometry, headMaterial);
    this.assistant.add(head);
    
    // Eyes
    const eyeGeometry = new THREE.SphereGeometry(0.15, 16, 16);
    const eyeMaterial = new THREE.MeshStandardMaterial({ 
      color: 0xffffff,
      emissive: 0xffffff,
      emissiveIntensity: 0.5
    });
    
    const leftEye = new THREE.Mesh(eyeGeometry, eyeMaterial);
    leftEye.position.set(-0.3, 0.2, 0.85);
    this.assistant.add(leftEye);
    
    const rightEye = new THREE.Mesh(eyeGeometry, eyeMaterial);
    rightEye.position.set(0.3, 0.2, 0.85);
    this.assistant.add(rightEye);
    
    // Mouth (initially hidden)
    const mouthGeometry = new THREE.TorusGeometry(0.2, 0.05, 16, 32);
    const mouthMaterial = new THREE.MeshStandardMaterial({ 
      color: 0x0b3b5c,
      emissive: 0x0b3b5c,
      emissiveIntensity: 0.3
    });
    this.mouth = new THREE.Mesh(mouthGeometry, mouthMaterial);
    this.mouth.position.set(0, -0.3, 0.85);
    this.mouth.rotation.x = Math.PI;
    this.mouth.scale.set(1, 0.5, 1);
    this.assistant.add(this.mouth);
    
    // Antenna
    const antennaGeometry = new THREE.CylinderGeometry(0.05, 0.05, 0.5, 8);
    const antennaMaterial = new THREE.MeshStandardMaterial({ 
      color: 0xd4af37,
      roughness: 0.2,
      metalness: 0.8
    });
    const antenna = new THREE.Mesh(antennaGeometry, antennaMaterial);
    antenna.position.set(0, 1.2, 0);
    this.assistant.add(antenna);
    
    // Antenna ball
    const ballGeometry = new THREE.SphereGeometry(0.1, 16, 16);
    const ballMaterial = new THREE.MeshStandardMaterial({ 
      color: 0xd4af37,
      emissive: 0xd4af37,
      emissiveIntensity: 0.3
    });
    const ball = new THREE.Mesh(ballGeometry, ballMaterial);
    ball.position.set(0, 1.5, 0);
    this.assistant.add(ball);
    
    this.scene.add(this.assistant);
  }

  createParticles() {
    const particleCount = 50;
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    
    for (let i = 0; i < particleCount * 3; i += 3) {
      positions[i] = (Math.random() - 0.5) * 4;
      positions[i + 1] = (Math.random() - 0.5) * 4;
      positions[i + 2] = (Math.random() - 0.5) * 4;
    }
    
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    
    const material = new THREE.PointsMaterial({
      color: 0x71212d,
      size: 0.05,
      transparent: true,
      opacity: 0.6
    });
    
    this.particles = new THREE.Points(geometry, material);
    this.scene.add(this.particles);
  }

  addEventListeners() {
    // Mouse movement for eye tracking
    document.addEventListener('mousemove', (e) => {
      const rect = this.container.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      const y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      
      if (this.assistant) {
        this.assistant.rotation.y = x * 0.3;
        this.assistant.rotation.x = -y * 0.3;
      }
    });
    
    // Window resize
    window.addEventListener('resize', () => {
      this.camera.aspect = this.container.clientWidth / this.container.clientHeight;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
    });
    
    // Speaking state
    document.addEventListener('ai-speaking', () => {
      this.isSpeaking = true;
    });
    
    document.addEventListener('ai-silent', () => {
      this.isSpeaking = false;
    });
  }

  animate() {
    requestAnimationFrame(() => this.animate());
    
    // Gentle floating animation
    if (this.assistant) {
      this.assistant.position.y = Math.sin(Date.now() * 0.002) * 0.1;
      
      // Speaking animation
      if (this.isSpeaking && this.mouth) {
        this.mouth.scale.y = 0.5 + Math.sin(Date.now() * 0.01) * 0.3;
      } else if (this.mouth) {
        this.mouth.scale.y = 0.5;
      }
    }
    
    // Rotate particles
    if (this.particles) {
      this.particles.rotation.y += 0.002;
      this.particles.rotation.x += 0.001;
    }
    
    this.renderer.render(this.scene, this.camera);
  }
}

// Initialize AI assistant animation
document.addEventListener('DOMContentLoaded', () => {
  // Add 3D container to chat widget
  const chatWidget = document.querySelector('.chatbot-widget, [class*="chatbot"]');
  if (chatWidget) {
    const container = document.createElement('div');
    container.id = 'ai-assistant-3d';
    container.style.cssText = 'width: 100%; height: 200px; position: relative;';
    chatWidget.insertBefore(container, chatWidget.firstChild);
    
    new AIAssistantAnimation();
  }
});

// Add speaking events to chat widget
function setupSpeakingEvents() {
  const chatInput = document.querySelector('input[type="text"], textarea');
  const chatMessages = document.querySelector('[class*="message"], [class*="chat"]');
  
  if (chatInput) {
    chatInput.addEventListener('input', () => {
      document.dispatchEvent(new CustomEvent('ai-speaking'));
    });
    
    chatInput.addEventListener('blur', () => {
      document.dispatchEvent(new CustomEvent('ai-silent'));
    });
  }
}

document.addEventListener('DOMContentLoaded', setupSpeakingEvents);
