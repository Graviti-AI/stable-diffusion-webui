
function submit_postprocessing(){
    var id = randomId()
    localStorage.setItem("txt2img_task_id", id);
    res = []
    for(var i=0; i<arguments.length; i++){
        res.push(arguments[i])
    }
    res[0] = id
    return res
}
