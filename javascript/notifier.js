let notifierGlobalOptions = {
    position: "bottom-right",
    icons: {enabled: false},
    minDurations: {
        async: 30,
        "async-block": 30,
    },
};

var notifier = new AWN(notifierGlobalOptions);
