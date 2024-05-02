const realtimeData = {};
const realtimeDataCallbacks = [];

async function requestOrderInfo(interval) {
    const interval_ms = interval * 1000;
    const url = "/api/order_info";

    while (true) {
        try {
            const response = await fetchGet(url);
            if (!response.ok) {
                throw `'${url}' request failed in realtimeData`;
            }
            realtimeData.orderInfo = await response.json();

            for (let callback of realtimeDataCallbacks) {
                if (typeof callback === "function") {
                    try {
                        callback(realtimeData);
                    } catch (error) {
                        console.error(error);
                    }
                }
            }

            await PYTHON.asyncio.sleep(interval_ms);
        } catch (error) {
            console.error(error);
            await PYTHON.asyncio.sleep(interval_ms * 3);
        }
    }
}

onUiLoaded(() => requestOrderInfo(10));
