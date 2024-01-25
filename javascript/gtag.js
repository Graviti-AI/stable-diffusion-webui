function extractNumberFromGenerateButton(str) {
    const matches = str.match(/\d+/);

    if (matches && matches.length > 0) {
        return parseInt(matches[0], 10); // Convert the string to an integer
    }

    return null;
}

function addGenerateGtagEvent(selector, itemName) {
    const creditsInfo = document.querySelector(selector);
    const credits = extractNumberFromGenerateButton(creditsInfo.textContent);
    if (credits) {
        gtag("event", "spend_virtual_currency", {
            value: credits,
            virtual_currency_name: "credits",
            item_name: itemName,
        });
    }
}

function addUpgradeGtagEvent(itemId, itemName) {
    gtag("event", "begin_checkout", {
        items: [
            {
                item_id: itemId,
                item_name: itemName,
            },
        ],
    });
}

function addPopupGtagEvent(itemId, itemName) {
    gtag("event", "view_item", {
        items: [
            {
                item_id: itemId,
                item_name: itemName,
            },
        ],
    });
}

function sendPurchaseEvent(callback = null) {
    fetch(
      '/api/payments/latest',
      {
        method: 'GET',
        credentials: 'include',
      }
    )
    .then(response => {
      if (response.status === 200) {
        return response.json();
      }
      return Promise.reject(response);
    })
    .then((data) => {
        let promises = data.map(item => {
            return new Promise((resolve, reject) => {
                gtag("event", "purchase", {
                    transaction_id: item.payment_id,
                    value: item.payment_value,
                    tax: item.tax,
                    currency: "USD",
                    items: [{
                        item_id: item.product_id,
                        item_name: item.product_name,
                        discount: item.discount,
                        item_category: item.product_category,
                        price: item.price,
                        quantity: item.quantity
                    }],
                    event_callback: function() {
                        resolve();
                    }
                });
            });
        });

        Promise.all(promises).then(() => {
            if (typeof callback === 'function') {
                callback();
            }
            const paymentIds = data.map(item => {
              return {payment_id: item.payment_id}
            });
            fetch(
              '/api/payments/reported',
              {
                method: 'POST',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(paymentIds)
              }
            )
            .then(response => {
              if (response.status === 200) {
                return response.json();
              }
              return Promise.reject(response);
            })
            .catch((error) => {
                console.error('update purchase info error:', error);
            });
        }).catch(error => {
            console.error("sendPurchaseEvent error:", error);
            if (typeof callback === 'function') {
                callback();
            }
        });
    })
    .catch((error) => {
        console.error('sendPurchaseEvent error:', error);
        if (typeof callback === 'function') {
            callback();
        }
    });
}

onUiLoaded(function(){
    sendPurchaseEvent();
});
