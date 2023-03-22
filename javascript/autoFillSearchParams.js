class AutoFillSearchParams {
    searchParams = new URLSearchParams(location.search);
    result = '__prompt__ __negative_prompt__';
    paramsKeys = ['prompt', 'negative_prompt', 'width', 'height', 'seed', 'steps', 'sampler', 'cfg', 'clip_skip', 'batch_size', 'ensd'];
    excludeKeys = ['utm_source', 'utm_medium', 'utm_content', 'utm_campaign', '__theme', 'lora', 'l', 'ti', 't', 'hn', 'h', 'lycoris', 'y', 'share_id'];
    defaultWidth = 512;
    defaultHeight = 512;
    hasWidthOrHeightParam = false;

    joinParams(key, value) {
        if (key === 'checkpoint' || key === 'c') {
            this.result += `Model hash:${value},`;
            return;
        }

        if (key === 'ensd') {
            this.result += `${key.toUpperCase()}:${value},`;
            return;
        }

        if (key === 'cfg') {
            this.result += `CFG scale:${value},`;
            return;
        }

        if (key === 'width') {
            this.defaultWidth = value;
            this.hasWidthOrHeightParam = true;
            return;
        }

        if (key === 'height') {
            this.defaultHeight = value;
            this.hasWidthOrHeightParam = true;
            return;
        }

        // set to the front
        if (key === 'prompt') {
            this.result = this.result.replace('__prompt__', `${value}\r\n`);
            return;
        }
        const settingValue = `${key.replace('_', ' ').replace(key[0],key[0].toUpperCase())}:${value}`;
        if (key === 'negative_prompt') {
            this.result = this.result.replace('__negative_prompt__', `${settingValue}\r\n`);
            return;
        }

        this.result += `${settingValue},`;
    }

    initSearchParams() {
        for (const [key, value] of this.searchParams.entries()) {
            if (!this.excludeKeys.includes(key.toLowerCase())) {
                this.joinParams(key.toLowerCase(), value);
            }
        }
        if (this.hasWidthOrHeightParam) {
            this.result += `Size: ${this.defaultWidth}x${this.defaultHeight},`;
        }
        this.result = this.result.replace('__prompt__', '').replace('__negative_prompt__', '');
        return this.result;
    }
}

onUiLoaded(function(){
   const resultPromots = new AutoFillSearchParams().initSearchParams();
   const txt2imgDom = gradioApp().querySelector("#txt2img_prompt");
   const textareaDom = txt2imgDom.querySelector("textarea");
   textareaDom.value = resultPromots;
   // need to dispatch
   const event = new Event("input");
   textareaDom.dispatchEvent(event);
   resultPromots && setTimeout(() => {
     const event = new Event("click");
     document.querySelector("#paste").dispatchEvent(event);
   })
   
})
