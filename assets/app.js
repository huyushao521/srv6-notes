// 侧边栏开关 + 目录搜索 + 当前标题高亮
(function () {
  var body = document.body;
  var toggle = document.querySelector('.nav-toggle');
  if (toggle) {
    toggle.addEventListener('click', function () {
      body.classList.toggle('nav-open');
    });
    document.addEventListener('click', function (e) {
      if (body.classList.contains('nav-open') &&
          !e.target.closest('.sidebar') && !e.target.closest('.nav-toggle')) {
        body.classList.remove('nav-open');
      }
    });
  }

  var q = document.getElementById('q');
  if (q) {
    q.addEventListener('input', function () {
      var v = q.value.trim().toLowerCase();
      document.querySelectorAll('.sidebar li').forEach(function (li) {
        var t = li.textContent.toLowerCase();
        li.style.display = !v || t.indexOf(v) >= 0 ? '' : 'none';
      });
      document.querySelectorAll('.nav-group').forEach(function (g) {
        var vis = Array.prototype.some.call(g.querySelectorAll('li'), function (li) {
          return li.style.display !== 'none';
        });
        g.style.display = vis ? '' : 'none';
      });
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === '/' && document.activeElement !== q) {
        e.preventDefault();
        q.focus();
      }
    });
  }

  var tocLinks = Array.prototype.slice.call(document.querySelectorAll('.toc a'));
  if (tocLinks.length) {
    var heads = tocLinks.map(function (a) {
      return document.getElementById(decodeURIComponent(a.hash.slice(1)));
    });
    function onScroll() {
      var y = window.scrollY + 90, idx = 0;
      heads.forEach(function (h, i) {
        if (h && h.offsetTop <= y) idx = i;
      });
      tocLinks.forEach(function (a, i) {
        a.style.color = i === idx ? 'var(--accent)' : '';
        a.style.borderLeftColor = i === idx ? 'var(--accent)' : 'transparent';
      });
    }
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }
})();
