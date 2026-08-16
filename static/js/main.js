// DOMIORA Premium JavaScript - Main Animation Controller
// Animations disabled for performance

// Initialize Lenis Smooth Scroll (disabled)
const initSmoothScroll = () => {
  // Disabled for performance
  return;
};

// Initialize GSAP Animations (disabled)
const initGSAPAnimations = () => {
  // Disabled for performance
  return;
};

// Initialize 3D Card Effects (disabled for performance)
const init3DCards = () => {
  // Disabled for performance
  return;
};

// Initialize Living Backgrounds (disabled for performance)
const initLivingBackgrounds = () => {
  // Disabled for performance
  return;
};

// Initialize Light Particles (disabled for performance)
const initParticles = () => {
  // Disabled for performance
  return;
};

// Initialize Counter Animations (disabled for performance)
const initCounters = () => {
  // Disabled for performance
  return;
};

// Initialize Premium Buttons (disabled for performance)
const initPremiumButtons = () => {
  // Disabled for performance
  return;
};

// Main Initialization
document.addEventListener('DOMContentLoaded', () => {
  // All animations disabled for performance
  // initSmoothScroll();
  // initGSAPAnimations();
  // init3DCards();
  // initLivingBackgrounds();
  // initParticles();
  // initCounters();
  // initPremiumButtons();
  
  // Remove loading overlay immediately
  const loader = document.querySelector('.loading-overlay');
  if (loader) {
    loader.classList.add('hidden');
  }
});

// Re-initialize on page changes (for SPA-like behavior) - disabled
window.addEventListener('popstate', () => {
  // Disabled for performance
  return;
});
