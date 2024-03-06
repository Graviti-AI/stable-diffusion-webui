var chunkSize = 1024*1024; // bytes

function loading(file, chunkSize, callbackProgress, callbackFinal) {
    var offset = 0;
    var partial;
    var index = 0;

    if(file.size===0){
        callbackFinal();
    }
    var lastOffset = 0;
    var chunkReorder = 0;
    var chunkTotal = 0;

    // memory reordering
    var previous = [];
    function callbackRead_buffered(reader, file, evt, callbackProgress, callbackFinal){
        chunkTotal++;

        if(lastOffset !== reader.offset){
            // out of order
            previous.push({ offset: reader.offset, size: reader.size, result: reader.result});
            chunkReorder++;
            return;
        }

        function parseResult(offset, size, result) {
            lastOffset = offset + size;
            callbackProgress(result);
            if (offset + size >= file.size) {
                lastOffset = 0;
                callbackFinal();
            }
        }

        // in order
        parseResult(reader.offset, reader.size, reader.result);

        // resolve previous buffered
        var buffered = [{}]
        while (buffered.length > 0) {
            buffered = previous.filter(function (item) {
                return item.offset === lastOffset;
            });
            buffered.forEach(function (item) {
                parseResult(item.offset, item.size, item.result);
                previous.remove(item);
            })
        }

    }

    Array.prototype.remove = Array.prototype.remove || function(val){
        var i = this.length;
        while(i--){
            if (this[i] === val){
                this.splice(i,1);
            }
        }
    }

    while (offset < file.size) {
        partial = file.slice(offset, offset+chunkSize);
        var reader = new FileReader;
        reader.size = chunkSize;
        reader.offset = offset;
        reader.index = index;
        reader.onload = function(evt) {
            callbackRead_buffered(this, file, evt, callbackProgress, callbackFinal);
        };
        reader.readAsArrayBuffer(partial);
        offset += chunkSize;
        index += 1;
    }
}

function hashFile(file) {
    if(file===undefined){
        return;
    }
    var SHA256 = CryptoJS.algo.SHA256.create();
    var counter = 0;

    var hash_str = new Promise((resolve, reject) => {
        loading(file, chunkSize,
            function (data) {
                var wordBuffer = CryptoJS.lib.WordArray.create(data);
                SHA256.update(wordBuffer);
                counter += data.byteLength;
            }, function (data) {
                var encrypted = SHA256.finalize().toString();
                resolve(encrypted);
            });
    });
    return hash_str;
}
