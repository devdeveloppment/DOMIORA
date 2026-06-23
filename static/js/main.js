// DOMIORA Premium JavaScript - Main Animation Controller

// Initialize Lenis Smooth Scroll
const initSmoothScroll = () => {
  if (typeof Lenis !== 'undefined') {
    const lenis = new Lenis({
      duration: 1.2,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      direction: 'vertical',
      gestureDirection: 'vertical',
      smooth: true,
      mouseMultiplier: 1,
      smoothTouch: false,
      touchMultiplier: 2,
    });

    function raf(time) {
      lenis.raf(time);
      requestAnimationFrame(raf);
    }

    requestAnimationFrame(raf);

    // Integrate with GSAP ScrollTrigger
    if (typeof gsap !== 'undefined' && typeof ScrollTrigger !== 'undefined') {
      gsap.registerPlugin(ScrollTrigger);
      
      lenis.on('scroll', ScrollTrigger.update);
      
      gsap.ticker.add((time) => {
        lenis.raf(time * 1000);
      });

      gsap.ticker.lagSmoothing(0);
    }
  }
};

// Initialize GSAP Animations
const initGSAPAnimations = () => {
  if (typeof gsap === 'undefined') return;

  // Reveal animations on scroll
  gsap.utils.toArray('.reveal-up').forEach((elem) => {
    gsap.fromTo(elem, 
      { opacity: 0, y: 60 },
      {
        opacity: 1,
        y: 0,
        duration: 0.8,
        ease: 'power3.out',
        scrollTrigger: {
          trigger: elem,
          start: 'top 85%',
          toggleActions: 'play none none reverse'
        }
      }
    );
  });

  gsap.utils.toArray('.reveal-left').forEach((elem) => {
    gsap.fromTo(elem,
      { opacity: 0, x: -60 },
      {
        opacity: 1,
        x: 0,
        duration: 0.8,
        ease: 'power3.out',
        scrollTrigger: {
          trigger: elem,
          start: 'top 85%',
          toggleActions: 'play none none reverse'
        }
      }
    );
  });

  gsap.utils.toArray('.reveal-right').forEach((elem) => {
    gsap.fromTo(elem,
      { opacity: 0, x: 60 },
      {
        opacity: 1,
        x: 0,
        duration: 0.8,
        ease: 'power3.out',
        scrollTrigger: {
          trigger: elem,
          start: 'top 85%',
          toggleActions: 'play none none reverse'
        }
      }
    );
  });

  gsap.utils.toArray('.reveal-scale').forEach((elem) => {
    gsap.fromTo(elem,
      { opacity: 0, scale: 0.8 },
      {
        opacity: 1,
        scale: 1,
        duration: 0.8,
        ease: 'back.out(1.7)',
        scrollTrigger: {
          trigger: elem,
          start: 'top 85%',
          toggleActions: 'play none none reverse'
        }
      }
    );
  });

  // Parallax effects
  gsap.utils.toArray('.parallax-layer').forEach((layer) => {
    const speed = layer.dataset.speed || 0.5;
    gsap.to(layer, {
      y: (i, target) => -ScrollTrigger.maxScroll(window) * speed * target.dataset.speed || 0,
      ease: 'none',
      scrollTrigger: {
        trigger: layer.parentElement,
        start: 'top bottom',
        end: 'bottom top',
        scrub: true
      }
    });
  });

  // Header scroll effect
  const header = document.querySelector('.header-premium');
  if (header) {
    ScrollTrigger.create({
      start: 'top -80',
      end: 99999,
      toggleClass: { className: 'scrolled', targets: header }
    });
  }
};

// Initialize 3D Card Effects
const init3DCards = () => {
  const cards = document.querySelectorAll('.card-3d');
  
  cards.forEach(card => {
    card.addEventListener('mousemove', (e) => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      
      const centerX = rect.width / 2;
      const centerY = rect.height / 2;
      
      const rotateX = (y - centerY) / 10;
      const rotateY = (centerX - x) / 10;
      
      card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateZ(20px)`;
    });
    
    card.addEventListener('mouseleave', () => {
      card.style.transform = 'perspective(1000px) rotateX(0) rotateY(0) translateZ(0)';
    });
  });
};

// Initialize Living Backgrounds
const initLivingBackgrounds = () => {
  const backgrounds = document.querySelectorAll('.living-background');
  
  const images = [
    'https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=2000&q=80',
    'https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=2000&q=80',
    'https://images.unsplash.com/photo-1600566753190-17f0baa2a6c3?w=2000&q=80',
    'https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=2000&q=80',
    'https://images.unsplash.com/photo-1600573472550-8090b5e0745e?w=2000&q=80'
  ];
  
  backgrounds.forEach(bg => {
    let currentIndex = 0;
    const imgElement = bg.querySelector('img') || bg;
    
    setInterval(() => {
      currentIndex = (currentIndex + 1) % images.length;
      if (imgElement.tagName === 'IMG') {
        imgElement.style.opacity = '0';
        setTimeout(() => {
          imgElement.src = images[currentIndex];
          imgElement.style.opacity = '0.4';
        }, 500);
      } else {
        bg.style.setProperty('--bg-image', `url(${images[currentIndex]})`);
      }
    }, 5000);
  });
};

// Initialize Light Particles
const initParticles = () => {
  const container = document.querySelector('.particle-container');
  if (!container) return;
  
  for (let i = 0; i < 50; i++) {
    const particle = document.createElement('div');
    particle.className = 'particle';
    particle.style.left = Math.random() * 100 + '%';
    particle.style.animationDelay = Math.random() * 8 + 's';
    particle.style.animationDuration = (Math.random() * 4 + 6) + 's';
    container.appendChild(particle);
  }
};

// Initialize Counter Animations
const initCounters = () => {
  const counters = document.querySelectorAll('.counter');
  
  counters.forEach(counter => {
    const target = parseInt(counter.dataset.target) || 0;
    const duration = 2000;
    const startTime = performance.now();
    
    const updateCounter = (currentTime) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const easeProgress = 1 - Math.pow(1 - progress, 3);
      const current = Math.floor(easeProgress * target);
      
      counter.textContent = current.toLocaleString();
      
      if (progress < 1) {
        requestAnimationFrame(updateCounter);
      }
    };
    
    // Start animation when in view
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          requestAnimationFrame(updateCounter);
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.5 });
    
    observer.observe(counter);
  });
};

// Initialize Premium Buttons
const initPremiumButtons = () => {
  const buttons = document.querySelectorAll('.btn-premium');
  
  buttons.forEach(button => {
    button.addEventListener('mouseenter', (e) => {
      const rect = button.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      
      button.style.setProperty('--mouse-x', x + 'px');
      button.style.setProperty('--mouse-y', y + 'px');
    });
  });
};

// Main Initialization
document.addEventListener('DOMContentLoaded', () => {
  initSmoothScroll();
  initGSAPAnimations();
  init3DCards();
  initLivingBackgrounds();
  initParticles();
  initCounters();
  initPremiumButtons();
  
  // Remove loading overlay
  const loader = document.querySelector('.loading-overlay');
  if (loader) {
    setTimeout(() => {
      loader.classList.add('hidden');
    }, 500);
  }
});

// Re-initialize on page changes (for SPA-like behavior)
window.addEventListener('popstate', () => {
  setTimeout(() => {
    initGSAPAnimations();
    init3DCards();
  }, 100);
});
