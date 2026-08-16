// DOMIORA Progressive Scroll Animations
class ScrollAnimations {
  constructor() {
    this.init();
  }

  init() {
    this.setupScrollTrigger();
    this.setupFadeInAnimations();
    this.setupSlideInAnimations();
    this.setupScaleAnimations();
    this.setupStaggerAnimations();
  }

  setupScrollTrigger() {
    // Register GSAP ScrollTrigger
    if (typeof gsap !== 'undefined' && typeof ScrollTrigger !== 'undefined') {
      gsap.registerPlugin(ScrollTrigger);
    }
  }

  setupFadeInAnimations() {
    // Fade in from bottom
    const fadeElements = document.querySelectorAll('[data-fade-in]');
    
    fadeElements.forEach(element => {
      gsap.fromTo(element, 
        { 
          opacity: 0, 
          y: 50 
        },
        { 
          opacity: 1, 
          y: 0, 
          duration: 0.8, 
          ease: 'power2.out',
          scrollTrigger: {
            trigger: element,
            start: 'top 85%',
            toggleActions: 'play none none reverse'
          }
        }
      );
    });

    // Fade in from top
    const fadeDownElements = document.querySelectorAll('[data-fade-down]');
    
    fadeDownElements.forEach(element => {
      gsap.fromTo(element, 
        { 
          opacity: 0, 
          y: -50 
        },
        { 
          opacity: 1, 
          y: 0, 
          duration: 0.8, 
          ease: 'power2.out',
          scrollTrigger: {
            trigger: element,
            start: 'top 85%',
            toggleActions: 'play none none reverse'
          }
        }
      );
    });
  }

  setupSlideInAnimations() {
    // Slide in from left
    const slideLeftElements = document.querySelectorAll('[data-slide-left]');
    
    slideLeftElements.forEach(element => {
      gsap.fromTo(element, 
        { 
          opacity: 0, 
          x: -100 
        },
        { 
          opacity: 1, 
          x: 0, 
          duration: 0.8, 
          ease: 'power2.out',
          scrollTrigger: {
            trigger: element,
            start: 'top 85%',
            toggleActions: 'play none none reverse'
          }
        }
      );
    });

    // Slide in from right
    const slideRightElements = document.querySelectorAll('[data-slide-right]');
    
    slideRightElements.forEach(element => {
      gsap.fromTo(element, 
        { 
          opacity: 0, 
          x: 100 
        },
        { 
          opacity: 1, 
          x: 0, 
          duration: 0.8, 
          ease: 'power2.out',
          scrollTrigger: {
            trigger: element,
            start: 'top 85%',
            toggleActions: 'play none none reverse'
          }
        }
      );
    });
  }

  setupScaleAnimations() {
    // Scale up animation
    const scaleElements = document.querySelectorAll('[data-scale-up]');
    
    scaleElements.forEach(element => {
      gsap.fromTo(element, 
        { 
          opacity: 0, 
          scale: 0.8 
        },
        { 
          opacity: 1, 
          scale: 1, 
          duration: 0.6, 
          ease: 'back.out(1.7)',
          scrollTrigger: {
            trigger: element,
            start: 'top 85%',
            toggleActions: 'play none none reverse'
          }
        }
      );
    });
  }

  setupStaggerAnimations() {
    // Stagger animation for lists
    const staggerElements = document.querySelectorAll('[data-stagger]');
    
    staggerElements.forEach(container => {
      const children = container.children;
      const staggerDelay = parseFloat(container.getAttribute('data-stagger')) || 0.1;
      
      gsap.fromTo(children, 
        { 
          opacity: 0, 
          y: 30 
        },
        { 
          opacity: 1, 
          y: 0, 
          duration: 0.6, 
          stagger: staggerDelay, 
          ease: 'power2.out',
          scrollTrigger: {
            trigger: container,
            start: 'top 85%',
            toggleActions: 'play none none reverse'
          }
        }
      );
    });
  }
}

// Initialize scroll animations
document.addEventListener('DOMContentLoaded', () => {
  new ScrollAnimations();
});

// Add scroll animation attributes to elements
function addScrollAttributes() {
  // Add fade-in to sections
  const sections = document.querySelectorAll('section');
  sections.forEach(section => {
    if (!section.hasAttribute('data-fade-in')) {
      section.setAttribute('data-fade-in', '');
    }
  });
  
  // Add slide animations to cards
  const cards = document.querySelectorAll('.property-card, .dashboard-card');
  cards.forEach((card, index) => {
    if (!card.hasAttribute('data-slide-up')) {
      card.setAttribute('data-slide-up', '');
    }
  });
  
  // Add stagger to grid items
  const grids = document.querySelectorAll('.grid, [class*="grid"]');
  grids.forEach(grid => {
    if (!grid.hasAttribute('data-stagger')) {
      grid.setAttribute('data-stagger', '0.1');
    }
  });
}

document.addEventListener('DOMContentLoaded', addScrollAttributes);

// Intersection Observer fallback for basic scroll animations
function setupIntersectionObserver() {
  const observerOptions = {
    root: null,
    rootMargin: '0px',
    threshold: 0.1
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('animate-in');
        observer.unobserve(entry.target);
      }
    });
  }, observerOptions);

  const animatedElements = document.querySelectorAll('[data-animate]');
  animatedElements.forEach(element => {
    observer.observe(element);
  });
}

document.addEventListener('DOMContentLoaded', setupIntersectionObserver);
