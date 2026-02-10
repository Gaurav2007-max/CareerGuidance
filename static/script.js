document.addEventListener('DOMContentLoaded', () => {
    // Dark Mode Toggle
    const darkModeToggle = document.getElementById('darkModeToggle');
    const htmlElement = document.documentElement;
    
    // Check for saved dark mode preference or default to light mode
    const isDarkMode = localStorage.getItem('darkMode') === 'true';
    if (isDarkMode) {
        document.body.classList.add('dark-mode');
        darkModeToggle.innerHTML = '<i class="fas fa-sun"></i>';
    }
    
    darkModeToggle.addEventListener('click', () => {
        document.body.classList.toggle('dark-mode');
        const isNowDarkMode = document.body.classList.contains('dark-mode');
        localStorage.setItem('darkMode', isNowDarkMode);
        
        // Update icon
        if (isNowDarkMode) {
            darkModeToggle.innerHTML = '<i class="fas fa-sun"></i>';
        } else {
            darkModeToggle.innerHTML = '<i class="fas fa-moon"></i>';
        }
    });

    // Handle Goal Status Updates via AJAX
    const actionButtons = document.querySelectorAll('.goal-action');
    actionButtons.forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const goalId = btn.dataset.id;
            const status = btn.dataset.status;
            
            try {
                const response = await fetch(`/update_goal/${goalId}/${status}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                if (response.ok) {
                    location.reload(); // Refresh to update charts and lists
                } else {
                    alert('Failed to update goal status.');
                }
            } catch (err) {
                console.error('Error:', err);
            }
        });
    });

    // Handle Advice History Delete
    const deleteAdviceButtons = document.querySelectorAll('.delete-advice-btn');
    deleteAdviceButtons.forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            const adviceId = btn.dataset.id;
            
            if (!confirm('Are you sure you want to delete this advice entry?')) {
                return;
            }
            
            try {
                const response = await fetch(`/delete_advice/${adviceId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                if (response.ok) {
                    // Fade out the advice item and remove it
                    const adviceItem = btn.closest('li');
                    adviceItem.style.animation = 'fadeOut 0.5s ease-out';
                    setTimeout(() => {
                        adviceItem.remove();
                        // Check if list is now empty
                        const adviceList = document.querySelector('.advice-history ul');
                        if (adviceList && adviceList.children.length === 0) {
                            location.reload(); // Reload to show "no history" message
                        }
                    }, 500);
                } else {
                    alert('Failed to delete advice entry.');
                }
            } catch (err) {
                console.error('Error:', err);
                alert('Error deleting advice entry.');
            }
        });
    });

    // Charting Logic (if on dashboard)
    const ctx = document.getElementById('statsChart');
    if (ctx) {
        const achievedCount = parseInt(ctx.dataset.achieved);
        const missedCount = parseInt(ctx.dataset.missed);
        const pendingCount = parseInt(ctx.dataset.pending);

        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Achieved', 'Missed', 'Pending'],
                datasets: [{
                    data: [achievedCount, missedCount, pendingCount],
                    backgroundColor: ['#10b981', '#ef4444', '#f59e0b'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { position: 'bottom' }
                }
            }
        });
    }

    // Dynamic AI Prompt Length Visual
    const aiForm = document.getElementById('aiForm');
    if (aiForm) {
        aiForm.addEventListener('submit', () => {
            const btn = aiForm.querySelector('button');
            btn.innerHTML = 'AI thinking... <span class="loader"></span>';
            btn.disabled = true;
        });
    }
});
document.addEventListener('DOMContentLoaded', function () {
    const calendarEl = document.getElementById('goalCalendar');
    if (!calendarEl) return;

    // Set minimum height for calendar container
    calendarEl.style.minHeight = '500px';

    fetch('/api/goals')
        .then(res => res.json())
        .then(events => {
            if (!window.FullCalendar) {
                console.error('FullCalendar not loaded');
                return;
            }
            const calendar = new FullCalendar.Calendar(calendarEl, {
                initialView: 'dayGridMonth',
                headerToolbar: {
                    left: 'prev,next today',
                    center: 'title',
                    right: 'dayGridMonth,listMonth'
                },
                contentHeight: 'auto',
                events: events,
                eventDisplay: 'block'
            });
            calendar.render();
        })
        .catch(err => console.error('Failed to load goals:', err));
});
