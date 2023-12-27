// code related to showing and updating progressbar shown as the image is being made

function rememberGallerySelection() {

}

function getGallerySelectedIndex() {

}

function request(url, data, handler, errorHandler) {
    var xhr = new XMLHttpRequest();
    xhr.open("POST", url, true);
    xhr.setRequestHeader("Content-Type", "application/json");
    xhr.onreadystatechange = function() {
        if (xhr.readyState === 4) {
            if (xhr.status === 200) {
                try {
                    var js = JSON.parse(xhr.responseText);
                    handler(js);
                } catch (error) {
                    console.error(error);
                    errorHandler(xhr.status)
                }
            } else {
                errorHandler(xhr.status)
            }
        }
    };
    var js = JSON.stringify(data);
    xhr.send(js);
}

function pad2(x) {
    return x < 10 ? '0' + x : x;
}

function formatTime(secs) {
    if (secs > 3600) {
        return pad2(Math.floor(secs / 60 / 60)) + ":" + pad2(Math.floor(secs / 60) % 60) + ":" + pad2(Math.floor(secs) % 60);
    } else if (secs > 60) {
        return pad2(Math.floor(secs / 60)) + ":" + pad2(Math.floor(secs) % 60);
    } else {
        return Math.floor(secs) + "s";
    }
}

function setTitle(progress) {
    var title = 'Stable Diffusion';

    if (opts.show_progress_in_title && progress) {
        title = '[' + progress.trim() + '] ' + title;
    }

    if (document.title != title) {
        document.title = title;
    }
}

function uuidv4() {
  return ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c =>
    (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16)
  );
}

function randomId() {
    if (typeof crypto.randomUUID == "function") {
        return "task(" + crypto.randomUUID() +")";
    } else {
        return "task(" + uuidv4() +")";
    }
}

function checkQueue(response) {
    if (userTier != "Free") {
        return false;
    }
    if (!response.queued) {
        return false;
    }
    let result = response.textinfo.match(/^In queue\((\d+) ahead\)/);
    if (!result) {
        return false;
    }

    let ahead = Number(result[1]);
    if (ahead <= 1) {
        return false;
    }
    notifier.confirm(
        `Your task is in queue and ${ahead} tasks ahead, upgrade to shorten the queue and get faster service.`,
        () => {window.open("/user#/subscription?type=subscription", "_blank")},
        () => {},
        {
            labels: {
                confirm: 'Upgrade Now',
                confirmOk: 'Upgrade'
            }
        }
    );
    return true;
}

// starts sending progress requests to "/internal/progress" uri, creating progressbar above progressbarContainer element and
// preview inside gallery element. Cleans up all created stuff when the task is over and calls atEnd.
// calls onProgress every time there is a progress update
function requestProgress(id_task, progressbarContainer, gallery, atEnd, onProgress, inactivityTimeout = 60) {
    var dateStart = new Date();
    var wasEverActive = false;
    var parentProgressbar = progressbarContainer.parentNode;

    var divProgress = document.createElement('div');
    divProgress.className = 'progressDiv';
    divProgress.style.display = opts.show_progressbar ? "block" : "none";
    var divInner = document.createElement('div');
    divInner.className = 'progress';

    divProgress.appendChild(divInner);
    parentProgressbar.insertBefore(divProgress, progressbarContainer);

    var livePreview = null;

    var removeProgressBar = function() {
        if (!divProgress) return;

        setTitle("");
        parentProgressbar.removeChild(divProgress);
        if (gallery && livePreview) gallery.removeChild(livePreview);
        atEnd();

        divProgress = null;
    };

    var lastFailedAt = null;
    let is_queue_checked = false;
    var funProgress = function(id_task, id_live_preview=false) {
        request("./internal/progress", {id_task: id_task, id_live_preview: id_live_preview}, function(res) {
            lastFailedAt = null;
            if(res.completed){
                removeProgressBar();
                console.log("remove progress bar: res.completed");
                return;
            }

            if (!is_queue_checked) {
                is_queue_checked = checkQueue(res);
            }

            let progressText = "";

            divInner.style.width = ((res.progress || 0) * 100.0) + '%';
            divInner.style.background = res.progress ? "" : "transparent";

            if (res.progress > 0) {
                progressText = ((res.progress || 0) * 100.0).toFixed(0) + '%';
            }

            if (res.eta) {
                progressText += " ETA: " + formatTime(res.eta);
            }

            setTitle(progressText);

            if (res.textinfo && res.textinfo.indexOf("\n") == -1) {
                progressText = res.textinfo + " " + progressText;
            }

            divInner.textContent = progressText;

            var elapsedFromStart = (new Date() - dateStart) / 1000;

            if (res.active) wasEverActive = true;

            if (elapsedFromStart > inactivityTimeout && !res.queued && !res.active) {
                console.log("remove progress bar: elapsedFromStart > inactivityTimeout && !res.queued && !res.active");
                removeProgressBar();
                return;
            }
            if (divProgress && res.live_preview && gallery) {
                var img = new Image();
                img.onload = function() {
                    if (!livePreview) {
                        livePreview = document.createElement('div');
                        livePreview.className = 'livePreview';
                        gallery.insertBefore(livePreview, gallery.firstElementChild);
                    }

                    livePreview.appendChild(img);
                    if (livePreview.childElementCount > 2) {
                        livePreview.removeChild(livePreview.firstElementChild);
                    }
                };
                img.src = res.live_preview;
            }

            if (onProgress) {
                onProgress(res);
            }

            setTimeout(() => {
                funProgress(id_task, res.id_live_preview);
            }, opts.live_preview_refresh_period || 1000);
        }, function() {
            if(lastFailedAt == null) {
                lastFailedAt = new Date()
            }
            var failedElapsed = (new Date() - lastFailedAt) / 1000
            // network error: retry for 5m
            // server error: retry for 30s
            // retry interval is at least 15s
            if (failedElapsed < (status === 0 ? 60 * 5 : 30)) {
                console.log("progress request error")
                setTimeout(() => {
                    // reset dateStart to prevent progress is removed due to timeout
                    dateStart = new Date()
                    funProgress(id_task, id_live_preview)
                }, Math.min(Math.max(failedElapsed, 1), 15)*1000)
            } else {
                console.log("remove progress bar: progress request is failed")
                removeProgressBar()
            }
        });
    };
    funProgress(id_task, 0);
}
