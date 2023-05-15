// code related to showing and updating progressbar shown as the image is being made

function rememberGallerySelection(id_gallery){

}

function getGallerySelectedIndex(id_gallery){

}

function request(url, data, handler, errorHandler){
    var xhr = new XMLHttpRequest();
    var url = url;
    xhr.open("POST", url, true);
    xhr.setRequestHeader("Content-Type", "application/json");
    xhr.onreadystatechange = function () {
        if (xhr.readyState === 4) {
            if (xhr.status === 200) {
                try {
                    var js = JSON.parse(xhr.responseText);
                    handler(js)
                } catch (error) {
                    console.error(error);
                    errorHandler(xhr.status)
                }
            } else{
                errorHandler(xhr.status)
            }
        }
    };
    var js = JSON.stringify(data);
    xhr.send(js);
}

function pad2(x){
    return x<10 ? '0'+x : x
}

function formatTime(secs){
    if(secs > 3600){
        return pad2(Math.floor(secs/60/60)) + ":" + pad2(Math.floor(secs/60)%60) + ":" + pad2(Math.floor(secs)%60)
    } else if(secs > 60){
        return pad2(Math.floor(secs/60)) + ":" + pad2(Math.floor(secs)%60)
    } else{
        return Math.floor(secs) + "s"
    }
}

function setTitle(progress){
    var title = 'Stable Diffusion'

    if(opts.show_progress_in_title && progress){
        title = '[' + progress.trim() + '] ' + title;
    }

    if(document.title != title){
        document.title =  title;
    }
}


function randomId(){
    return "task(" + Math.random().toString(36).slice(2, 9) + Math.random().toString(36).slice(2, 9) + Math.random().toString(36).slice(2, 9)+")"
}

// starts sending progress requests to "/internal/progress" uri, creating progressbar above progressbarContainer element and
// preview inside gallery element. Cleans up all created stuff when the task is over and calls atEnd.
// calls onProgress every time there is a progress update
function requestProgress(id_task, progressbarContainer, gallery, atEnd, onProgress, inactivityTimeout=60){
    var dateStart = new Date()
    var wasEverActive = false
    var parentProgressbar = progressbarContainer.parentNode
    var parentGallery = gallery ? gallery.parentNode : null

    var divProgress = document.createElement('div')
    divProgress.className='progressDiv'
    divProgress.style.display = opts.show_progressbar ? "block" : "none"
    var divInner = document.createElement('div')
    divInner.className='progress'

    divProgress.appendChild(divInner)
    parentProgressbar.insertBefore(divProgress, progressbarContainer)

    if(parentGallery){
        var livePreview = document.createElement('div')
        livePreview.className='livePreview'
        parentGallery.insertBefore(livePreview, gallery)
    }

    var removeProgressBar = function(){
        setTitle("")
        parentProgressbar.removeChild(divProgress)
        if(parentGallery) parentGallery.removeChild(livePreview)
        atEnd()
    }

    var lastFailedAt = null
    var fun = function(id_task, id_live_preview){
        request("./internal/progress", {"id_task": id_task, "id_live_preview": id_live_preview}, function(res){
             lastFailedAt = null
            if(res.completed){
                removeProgressBar()
                console.log("remove progress bar: res.completed")
                return
            }

            var rect = progressbarContainer.getBoundingClientRect()

            if(rect.width){
                divProgress.style.width = rect.width + "px";
            }

            progressText = ""

            divInner.style.width = ((res.progress || 0) * 100.0) + '%'
            divInner.style.background = res.progress ? "" : "transparent"

            if(res.progress > 0){
                progressText = ((res.progress || 0) * 100.0).toFixed(0) + '%'
            }

            if(res.eta){
                progressText += " ETA: " + formatTime(res.eta)
            }


            setTitle(progressText)

            if(res.textinfo && res.textinfo.indexOf("\n") == -1){
                progressText = res.textinfo + " " + progressText
            }

            divInner.textContent = progressText

            var elapsedFromStart = (new Date() - dateStart) / 1000

            if(res.active) wasEverActive = true;

            if(! res.active && wasEverActive){
                removeProgressBar()
                console.log("remove progress bar: ! res.active && wasEverActive")
                return
            }

            if(elapsedFromStart > inactivityTimeout && !res.queued && !res.active){
                console.log("remove progress bar: elapsedFromStart > inactivityTimeout && !res.queued && !res.active")
                removeProgressBar()
                return
            }

            if(res.live_preview && gallery){
                var rect = gallery.getBoundingClientRect()
                if(rect.width){
                    livePreview.style.width = rect.width + "px"
                    livePreview.style.height = rect.height + "px"
                }

                var img = new Image();
                img.onload = function() {
                    livePreview.appendChild(img)
                    if(livePreview.childElementCount > 2){
                        livePreview.removeChild(livePreview.firstElementChild)
                    }
                }
                img.src = res.live_preview;
            }

            if(onProgress){
                onProgress(res)
            }

            setTimeout(() => {
                fun(id_task, res.id_live_preview);
            }, opts.live_preview_refresh_period || 500)
        }, function(status){
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
                    fun(id_task, res.id_live_preview)
                }, Math.min(Math.max(failedElapsed, 1), 15)*1000)
            } else {
                console.log("remove progress bar: progress request is failed")
                removeProgressBar()
            }
        })
    }

    fun(id_task, 0)
}
