// DOMIORA Modern Interactive Map with Relief
class InteractiveMap {
  constructor() {
    this.init();
  }

  init() {
    this.setupMap();
    this.setupReliefEffect();
    this.setupPropertyMarkers();
    this.setupMapInteractions();
  }

  setupMap() {
    // Find map container
    const mapContainer = document.querySelector('[data-interactive-map]');
    if (!mapContainer) return;

    // Initialize Leaflet map if available
    if (typeof L !== 'undefined') {
      this.initLeafletMap(mapContainer);
    } else {
      // Fallback to custom map
      this.initCustomMap(mapContainer);
    }
  }

  initLeafletMap(container) {
    const map = L.map(container).setView([6.1319, 1.2225], 13); // Lomé, Togo coordinates

    // Add tile layer with custom style
    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
      subdomains: 'abcd',
      maxZoom: 19
    }).addTo(map);

    // Add relief effect
    this.addReliefLayer(map);

    // Add property markers
    this.addPropertyMarkersToMap(map);
  }

  initCustomMap(container) {
    // Create custom 3D map using Three.js
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(75, container.clientWidth / container.clientHeight, 0.1, 1000);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);
    
    camera.position.set(0, 10, 10);
    camera.lookAt(0, 0, 0);
    
    // Create terrain
    this.createTerrain(scene);
    
    // Add buildings
    this.createBuildings(scene);
    
    // Add property markers
    this.create3DPropertyMarkers(scene);
    
    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
    scene.add(ambientLight);
    
    const directionalLight = new THREE.DirectionalLight(0x71212d, 0.8);
    directionalLight.position.set(10, 20, 10);
    scene.add(directionalLight);
    
    // Animation
    const animate = () => {
      requestAnimationFrame(animate);
      renderer.render(scene, camera);
    };
    
    animate();
    
    // Mouse interaction
    this.setupMapControls(scene, camera, renderer, container);
  }

  createTerrain(scene) {
    // Create terrain with relief
    const geometry = new THREE.PlaneGeometry(20, 20, 32, 32);
    
    // Add height variation for relief effect
    const vertices = geometry.attributes.position.array;
    for (let i = 0; i < vertices.length; i += 3) {
      vertices[i + 2] = Math.sin(vertices[i] * 0.5) * Math.cos(vertices[i + 1] * 0.5) * 2;
    }
    
    geometry.computeVertexNormals();
    
    const material = new THREE.MeshStandardMaterial({ 
      color: 0x90a955,
      roughness: 0.8,
      metalness: 0.1,
      side: THREE.DoubleSide
    });
    
    const terrain = new THREE.Mesh(geometry, material);
    terrain.rotation.x = -Math.PI / 2;
    scene.add(terrain);
  }

  createBuildings(scene) {
    const buildingMaterial = new THREE.MeshStandardMaterial({ 
      color: 0x71212d,
      roughness: 0.6,
      metalness: 0.2
    });
    
    // Create random buildings
    for (let i = 0; i < 20; i++) {
      const height = Math.random() * 3 + 1;
      const width = Math.random() * 1 + 0.5;
      const depth = Math.random() * 1 + 0.5;
      
      const geometry = new THREE.BoxGeometry(width, height, depth);
      const building = new THREE.Mesh(geometry, buildingMaterial);
      
      building.position.x = (Math.random() - 0.5) * 15;
      building.position.z = (Math.random() - 0.5) * 15;
      building.position.y = height / 2;
      
      scene.add(building);
    }
  }

  create3DPropertyMarkers(scene) {
    const markerMaterial = new THREE.MeshStandardMaterial({ 
      color: 0xd4af37,
      emissive: 0xd4af37,
      emissiveIntensity: 0.3
    });
    
    // Create property markers
    for (let i = 0; i < 5; i++) {
      const geometry = new THREE.ConeGeometry(0.3, 1, 32);
      const marker = new THREE.Mesh(geometry, markerMaterial);
      
      marker.position.x = (Math.random() - 0.5) * 10;
      marker.position.z = (Math.random() - 0.5) * 10;
      marker.position.y = 0.5;
      
      scene.add(marker);
    }
  }

  addReliefLayer(map) {
    // Add hillshade layer for relief effect
    const reliefLayer = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      opacity: 0.3,
      attribution: ''
    });
    
    reliefLayer.addTo(map);
  }

  addPropertyMarkersToMap(map) {
    // Sample property locations (replace with actual data)
    const properties = [
      { lat: 6.1319, lng: 1.2225, title: 'Villa de Luxe', price: '50M FCFA' },
      { lat: 6.1350, lng: 1.2250, title: 'Appartement Moderne', price: '25M FCFA' },
      { lat: 6.1280, lng: 1.2200, title: 'Terrain Constructible', price: '15M FCFA' },
      { lat: 6.1400, lng: 1.2300, title: 'Bureau Commercial', price: '80M FCFA' },
      { lat: 6.1250, lng: 1.2150, title: 'Maison Familiale', price: '35M FCFA' }
    ];
    
    properties.forEach(property => {
      const marker = L.marker([property.lat, property.lng]).addTo(map);
      
      const popupContent = `
        <div class="p-2">
          <h3 class="font-bold text-sm">${property.title}</h3>
          <p class="text-xs text-gray-600">${property.price}</p>
          <a href="#" class="text-xs text-blue-600 hover:underline">Voir détails</a>
        </div>
      `;
      
      marker.bindPopup(popupContent);
    });
  }

  setupReliefEffect() {
    // Add CSS-based relief effect to map containers
    const mapContainers = document.querySelectorAll('[data-interactive-map]');
    
    mapContainers.forEach(container => {
      container.style.cssText += `
        position: relative;
        overflow: hidden;
        border-radius: 16px;
        box-shadow: 
          0 10px 40px rgba(0, 0, 0, 0.2),
          inset 0 1px 0 rgba(255, 255, 255, 0.1);
      `;
      
      // Add gradient overlay for depth
      const overlay = document.createElement('div');
      overlay.style.cssText = `
        position: absolute;
        inset: 0;
        background: linear-gradient(135deg, rgba(113, 33, 45, 0.1) 0%, transparent 50%, rgba(11, 59, 92, 0.1) 100%);
        pointer-events: none;
        z-index: 1;
      `;
      container.appendChild(overlay);
    });
  }

  setupPropertyMarkers() {
    // Add animated property markers to existing maps
    const markers = document.querySelectorAll('[data-property-marker]');
    
    markers.forEach(marker => {
      marker.style.cssText = `
        position: relative;
        animation: markerPulse 2s ease-in-out infinite;
      `;
    });
    
    // Add pulse animation
    const style = document.createElement('style');
    style.textContent = `
      @keyframes markerPulse {
        0%, 100% { transform: scale(1); opacity: 1; }
        50% { transform: scale(1.2); opacity: 0.8; }
      }
    `;
    document.head.appendChild(style);
  }

  setupMapInteractions() {
    // Add hover effects to map elements
    const mapElements = document.querySelectorAll('[data-interactive-map] *');
    
    mapElements.forEach(element => {
      element.addEventListener('mouseenter', () => {
        gsap.to(element, {
          scale: 1.05,
          duration: 0.3,
          ease: 'power2.out'
        });
      });
      
      element.addEventListener('mouseleave', () => {
        gsap.to(element, {
          scale: 1,
          duration: 0.3,
          ease: 'power2.out'
        });
      });
    });
  }

  setupMapControls(scene, camera, renderer, container) {
    let isDragging = false;
    let previousMousePosition = { x: 0, y: 0 };
    
    container.addEventListener('mousedown', (e) => {
      isDragging = true;
      previousMousePosition = { x: e.clientX, y: e.clientY };
    });
    
    container.addEventListener('mousemove', (e) => {
      if (!isDragging) return;
      
      const deltaX = e.clientX - previousMousePosition.x;
      const deltaY = e.clientY - previousMousePosition.y;
      
      camera.position.x -= deltaX * 0.01;
      camera.position.y += deltaY * 0.01;
      
      previousMousePosition = { x: e.clientX, y: e.clientY };
    });
    
    container.addEventListener('mouseup', () => {
      isDragging = false;
    });
    
    container.addEventListener('mouseleave', () => {
      isDragging = false;
    });
    
    // Zoom with scroll
    container.addEventListener('wheel', (e) => {
      e.preventDefault();
      camera.position.z += e.deltaY * 0.01;
      camera.position.z = Math.max(5, Math.min(20, camera.position.z));
    });
  }
}

// Initialize interactive map
document.addEventListener('DOMContentLoaded', () => {
  new InteractiveMap();
});

// Add map attributes to existing map containers
function addMapAttributes() {
  const mapContainers = document.querySelectorAll('.map, [class*="map"], iframe[src*="map"]');
  mapContainers.forEach(container => {
    if (!container.hasAttribute('data-interactive-map')) {
      container.setAttribute('data-interactive-map', '');
    }
  });
}

document.addEventListener('DOMContentLoaded', addMapAttributes);
