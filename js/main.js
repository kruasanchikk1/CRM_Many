// Плавное появление секций при скролле
function revealSectionsOnScroll() {
  const reveals = document.querySelectorAll(
    '.benefits, .how-works, .audience, .cta, .features-list, .pricing-row, .contact-form-section, .contacts-block'
  );
  for (let block of reveals) {
    if (block.getBoundingClientRect().top < window.innerHeight - 60) {
      block.style.opacity = 1;
      block.style.transform = 'translateY(0)';
    } else {
      block.style.opacity = 0.2;
      block.style.transform = 'translateY(80px)';
    }
  }
}
window.addEventListener('scroll', revealSectionsOnScroll);
window.addEventListener('DOMContentLoaded', () => {
  // Первичная анимация
  revealSectionsOnScroll();
  // Красивые кнопки: ripple
  document.querySelectorAll('.btn').forEach(btn => {
    btn.addEventListener('click', function (e) {
      const circle = document.createElement('span');
      circle.className = 'ripple';
      circle.style.left = e.offsetX + 'px';
      circle.style.top = e.offsetY + 'px';
      this.appendChild(circle);
      setTimeout(() => circle.remove(), 600);
    });
  });
  // Обработка submit для формы (демо)
  const form = document.querySelector('.contact-form');
  if (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      alert('Спасибо за обращение! Мы свяжемся с вами в ближайшее время.');
      form.reset();
    });
  }
});
// Ripple-эффект через CSS, если такого класса нет, вставьте ниже в style.css:
// .ripple {
//   position: absolute; pointer-events: none; border-radius: 50%; transform: scale(0);
//   animation: ripple 0.6s linear; background: rgba(61,90,254,0.23); width: 100px; height: 100px;
//   left: 50%; top: 50%;
// }
// @keyframes ripple { to { transform: scale(2.2); opacity: 0; } }
