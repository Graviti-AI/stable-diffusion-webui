class SignForCredits {
    async sign() {
        const signNode = gradioApp().querySelector(".user-content #sign");
        try {
            const response = await fetch(`/api/user_sign`, {method: "POST", credentials: "include"});
            const { gained_inference_count, continue_signed_days } = await response.json();
            if (continue_signed_days === 1) {
                notifier.success('Get extra 5 credits tomorrow,<a href="/user#/billing">See Details</a>')
            } else if (continue_signed_days >= 2 && continue_signed_days <= 6) {
                notifier.success(`Extra ${gained_inference_count} Credits today. Get extra 5 credits tomorrow<p><a href="/user#/billing">See Details</a></p>`)
            } else {
                notifier.success(`Congratulations! Extra ${gained_inference_count} Credits today,Earn extra 30 credits daily<p><a href="/user#/billing">See Details</a></p>`)
            }   
            signNode.style.display = 'none';
        } catch(e) {
            notifier.alert('check in error');
        }
    }
    async showActivityButtonForUser() {
        const signNode = gradioApp().querySelector(".user-content #sign");
        const linkNode = signNode.querySelector('a');
        const imgNode = signNode.querySelector('img');
        const spanNode = signNode.querySelector('span');
        const upgradeBtnNode = gradioApp().querySelector("#upgrade span");
        try {
            if (!isPcScreen) {
                upgradeBtnNode.textContent = '';
            }
            const response = await fetch(`/api/user_sign`, {method: "GET", credentials: "include"});
            const { has_sign_permission, has_signed_today } = await response.json();
            if (!has_sign_permission) {
                signNode.title = 'Unlock up to 1500 free credits per month';
                imgNode.src = '/public/image/unlock.png';
                spanNode.textContent = isPcScreen ? 'Free Credits' : '';
                signNode.style.display = 'flex';
                linkNode.href = PRICING_URL;
            } else {
                // set after reload
                if (Cookies && Cookies.get(languageCookieKey)) {
                    if (localStorage.getItem('show-data-survey-info') !== 'true') {
                        notifier.info('Help us improve our product and get a 20% discount coupon. <a href="/user#/billing"> Start Survey</a>',  {durations: {info: 0}});
                        localStorage.setItem('show-data-survey-info', 'true');
                    }
                }
                if (!has_signed_today) {
                    signNode.title = 'Unlock up to 900 free credits per month';
                    imgNode.src = '/public/image/calendar.png';
                    spanNode.textContent = isPcScreen ? 'Check-in' : '';
                    signNode.style.display = 'flex';
                    linkNode.addEventListener('click', this.sign);
                }
            }
            
        }catch(e) {
            console.log(e)
        }
    }
}

onUiLoaded(function(){
    new SignForCredits().showActivityButtonForUser();
})