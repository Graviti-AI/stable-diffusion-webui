let itemsMapping = {};
let itemsInLists = {};

function getItemsMapping(callback = null) {
  fetch("/api/analytics/items", {
    method: "GET",
    credentials: "include",
  })
    .then((response) => {
      if (response.status === 200) {
        return response.json();
      }
      return Promise.reject(response);
    })
    .then((data) => {
      itemsMapping = data.items_mapping;
      itemsInLists = data.items_in_lists;
      if (typeof callback === "function") {
        callback();
      }
    })
    .catch((error) => {
      console.error("loadItemMappingError error:", error);
      if (typeof callback === "function") {
        callback();
      }
    });
}

function ttqTrack(event, data) {
  const date = new Date();
  const eventId = randomUUID().replace(/-/g, '');
  const urlSearchParams = new URLSearchParams(window.location.search);
  const ttclidValue = urlSearchParams.get("ttclid");
  let url = "/api/analytics/ttq";
  if (ttclidValue) {
    url =
      "/api/analytics/ttq?" +
      new URLSearchParams({
        ttclid: ttclidValue,
      });
  }
  fetch(url, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      event: event,
      event_time: Math.floor(date.getTime() / 1000),
      event_id: eventId,
      page: {
        url: window.location.href,
      },
      contents: data.contents,
      value: data.value,
      currency: data.currency,
      query: data.query,
    }),
  })
    .then((response) => {
      if (response.status === 200) {
        return response.json();
      }
      return Promise.reject(response);
    })
    .catch((error) => {
      console.error("reportCheckout error:", error);
    })
    .finally(() => {
      if (typeof ttq.track === "function") {
        try {
          ttq.track(event, data, {event_id: eventId});
        } catch (error) {
          console.error(error);
        }
      }
    });
}

function reportCheckout(listUniqueId, listName, brandName, callback = null) {
  const date = new Date();
  fetch("/api/analytics/checkout", {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      list_id: listUniqueId,
      list_name: listName,
      item_brand: brandName,
      created_at: date.toISOString(),
    }),
  })
    .then((response) => {
      if (response.status === 200) {
        return response.json();
      }
      return Promise.reject(response);
    })
    .then((data) => {
      if (typeof callback === "function") {
        callback();
      }
    })
    .catch((error) => {
      console.error("reportCheckout error:", error);
    });
}

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
    if (typeof ttqTrack === "function") {
      const domain = window.location.hostname;
      ttqTrack("ClickButton", {
        contents: [
          {
            content_id: domain + ":" + itemName,
            content_type: "product_group",
            content_name: itemName,
            content_category: "generate_button",
          },
        ],
        query: selector,
      });
    }
  }
}

function getItemUniqueId(listID) {
  for (let key in itemsMapping) {
    if (listID.includes(key)) {
      return itemsMapping[key];
    }
  }
  return null;
}

function getProductInformation(listId, listName) {
  const listUniqueId = getItemUniqueId(listId) || listId;
  const domain = window.location.protocol + "//" + window.location.host;
  let items = [];
  if (itemsInLists[listUniqueId]) {
    items = itemsInLists[listUniqueId].map((item) => {
      return {
        item_id: item.item_id,
        item_name: item.item_name,
        item_brand: domain,
        item_category: item.item_category,
        item_list_id: listUniqueId,
        item_list_name: listName,
        price: item.price,
        quantity: item.quantity,
      };
    });
  } else {
    items = [
      {
        item_id: listUniqueId,
        item_name: listName,
      },
    ];
  }
  return {
    listUniqueId: listUniqueId,
    listName: listName,
    domain: domain,
    items: items,
  };
}

function addUpgradeGtagEvent(listId, listName, callback = null) {
  const { listUniqueId, domain, items } = getProductInformation(
    listId,
    listName,
  );
  gtag("event", "begin_checkout", {
    items: items,
    event_callback: function () {
      reportCheckout(listUniqueId, listName, domain, (callback = callback));
    },
  });
  if (typeof ttqTrack === "function") {
    const contents = items.map((item) => {
      return {
        content_id: item.item_id,
        content_type: "product",
        content_name: item.item_name,
        content_category: item.item_category,
        quantity: item.quantity,
        price: item.price,
      };
    });
    const total_value = items.reduce((total, item) => {
      if (item.price && item.quantity) {
        return total + item.price * item.quantity;
      } else {
        return total;
      }
    }, 0);
    try {
      ttqTrack("InitiateCheckout", {
        contents: contents,
        value: total_value,
        currency: "USD",
        query: "pricing_table",
      });
    } catch (error) {
      console.error(error);
    }
  }
}

function addPopupGtagEvent(listId, listName, callback = null) {
  const { listUniqueId, items } = getProductInformation(listId, listName);
  gtag("event", "view_item_list", {
    item_list_id: listUniqueId,
    item_list_name: listName,
    items: items,
    event_callback: function () {
      if (typeof callback === "function") {
        callback();
      }
    },
  });
  if (typeof ttqTrack === "function") {
    const contents = items.map((item) => {
      return {
        content_id: item.item_id,
        content_type: "product",
        content_name: item.item_name,
        content_category: item.item_category,
        quantity: item.quantity,
        price: item.price,
      };
    });
    const total_value = items.reduce((total, item) => {
      if (item.price && item.quantity) {
        return total + item.price * item.quantity;
      } else {
        return total;
      }
    }, 0);
    try {
      ttqTrack("AddToCart", {
        contents: contents,
        value: total_value,
        currency: "USD",
        query: listName,
      });
    } catch (error) {
      console.error(error);
    }
  }
}

function sendPurchaseEvent(callback = null) {
  fetch("/api/payments/latest", {
    method: "GET",
    credentials: "include",
  })
    .then((response) => {
      if (response.status === 200) {
        return response.json();
      }
      return Promise.reject(response);
    })
    .then(async (data) => {
      const resp = await fetchGet("/api/analytics/item_lists");
      let promises = [];
      if (resp.status === 200) {
        const itemLists = await resp.json();
        promises = data.map((item) => {
          let listInfo = {};
          for (let i = itemLists.length - 1; i >= 0; i--) {
            listInfo = itemLists[i];
            if (
              itemsInLists[listInfo.list_id].some(
                (listItem) => listItem.item_id === item.product_id,
              )
            ) {
              break;
            }
          }
          return new Promise((resolve, reject) => {
            gtag("event", "purchase", {
              transaction_id: item.payment_id,
              value: item.payment_value,
              tax: item.tax,
              currency: "USD",
              items: [
                {
                  item_id: item.product_id,
                  item_name: item.product_name,
                  discount: item.discount,
                  item_category: item.product_category,
                  price: item.price,
                  quantity: item.quantity,
                  item_list_id: listInfo.list_id || "unknown",
                  item_list_name: listInfo.list_name || "unknown",
                  item_brand:
                    listInfo.item_brand ||
                    window.location.protocol + "//" + window.location.host,
                },
              ],
              event_callback: function () {
                resolve();
              },
            });
            if (typeof ttqTrack === "function") {
              try {
                ttqTrack("CompletePayment", {
                  contents: [
                    {
                      content_id: item.product_id,
                      content_type: "product",
                      content_name: item.product_name,
                      content_category: item.product_category,
                      quantity: item.quantity,
                      price: item.price,
                    },
                  ],
                  value: item.payment_value,
                  currency: "USD",
                  query: listInfo.list_name || "unknown",
                });
              } catch (error) {
                console.error(error);
              }
            }
          });
        });
      } else {
        promises = data.map((item) => {
          return new Promise((resolve, reject) => {
            gtag("event", "purchase", {
              transaction_id: item.payment_id,
              value: item.payment_value,
              tax: item.tax,
              currency: "USD",
              items: [
                {
                  item_id: item.product_id,
                  item_name: item.product_name,
                  discount: item.discount,
                  item_category: item.product_category,
                  price: item.price,
                  quantity: item.quantity,
                },
              ],
              event_callback: function () {
                resolve();
              },
            });
            if (typeof ttqTrack === "function") {
              try {
                ttqTrack("CompletePayment", {
                  contents: [
                    {
                      content_id: item.product_id,
                      content_type: "product",
                      content_name: item.product_name,
                      content_category: item.product_category,
                      quantity: item.quantity,
                      price: item.price,
                    },
                  ],
                  value: item.payment_value,
                  currency: "USD",
                  query: "unknown",
                });
              } catch (error) {
                console.error(error);
              }
            }
          });
        });
      }
      if (window.gaIsBlocked) {
        if (typeof callback === "function") {
          callback();
        }
        return;
      }

      Promise.all(promises)
        .then(() => {
          if (typeof callback === "function") {
            callback();
          }
          const paymentIds = data.map((item) => {
            return { payment_id: item.payment_id };
          });
          fetch("/api/payments/reported", {
            method: "POST",
            credentials: "include",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(paymentIds),
          })
            .then((response) => {
              if (response.status === 200) {
                return response.json();
              }
              return Promise.reject(response);
            })
            .catch((error) => {
              console.error("update purchase info error:", error);
            });
        })
        .catch((error) => {
          console.error("sendPurchaseEvent error:", error);
          if (typeof callback === "function") {
            callback();
          }
        });
    })
    .catch((error) => {
      console.error("sendPurchaseEvent error:", error);
      if (typeof callback === "function") {
        callback();
      }
    });
}

let ttqCallbacks = [];

function onTtqIdentify(callback) {
  ttqCallbacks.push(callback);
}

async function reportIdentity(userId, userEmail) {
  if (typeof ttq.identify === "function") {
    try {
      ttq.identify({
        email: await sha256(userEmail.toLowerCase()),
        external_id: await sha256(userId),
      });
      Promise.all(ttqCallbacks.map(func => func()))
      .catch(error => {
        console.error('A promise has rejected', error);
      });
    } catch (error) {
      console.error(error);
    }
  }
}

async function reportViewContent() {
  const domain = window.location.hostname;
  const path = window.location.pathname;
  const queryString = window.location.search;
  const pageFull = domain + "/" + path;
  const page_id = await sha256(pageFull);
  if (typeof ttqTrack === "function") {
    try {
      ttqTrack("ViewContent", {
        contents: [
          {
            content_id: page_id,
            content_type: "product_group",
            content_name: path,
            content_category: domain,
          },
        ],
        query: queryString,
      });
    } catch (error) {
      console.error(error);
    }
  }
}

async function reportCompleteRegistration() {
  const domain = window.location.hostname;
  const path = window.location.pathname;
  const queryString = window.location.search;
  const pageFull = domain + "/" + path;
  const page_id = await sha256(pageFull);
  if (typeof ttqTrack === "function") {
    try {
      ttqTrack("CompleteRegistration", {
        contents: [
          {
            content_id: page_id,
            content_type: "product_group",
            content_name: path,
            content_category: domain,
          },
        ],
        query: queryString,
      });
      Cookies.set("_complete_registration", "true", { expires: 365 });
    } catch (error) {
      console.error(error);
    }
  }
}

onTtqIdentify(async function () {
  getItemsMapping(
    (callback = function () {
      sendPurchaseEvent();
    }),
  );
  await reportViewContent();
  const completeRegistration = Cookies.get('_complete_registration');
  if (!completeRegistration) {
      await reportCompleteRegistration();
  }
});
