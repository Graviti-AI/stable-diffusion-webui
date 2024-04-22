var systemMonitorState = {
  tab_txt2img: {
    generate_button_id: "txt2img_generate",
    timeout_id: null,
    functions: {
      "modules.txt2img.txt2img": {
        params: {
          'steps': 20,
          'restore_faces': false,
          'n_iter': 1,
          'batch_size': 4,
          "width": 512,
          "height": 512,
          'enable_hr': false,
          'hr_scale': 2,
          'hr_second_pass_steps': 20,
          'hr_resize_x': 0,
          'hr_resize_y': 0,
        },
        link_params: {}, // tab_name: function_name
        mutipliers: {}, // multipler_name: value
        link_mutipliers: {}, // function_name: param_name
      }
    }
  },
  tab_img2img: {
    generate_button_id: "img2img_generate",
    timeout_id: null,
    functions: {
      "modules.img2img.img2img" : {
        params: {
          'steps': 20,
          'restore_faces': false,
          'n_iter': 1,
          'batch_size': 4,
          "width": 512,
          "height": 512,
        },
        link_params: {}, // tab_name: function_name
        mutipliers: {}, // multipler_name: value
        link_mutipliers: {}, // function_name: param_name
      }
    }
  },
  tab_extras: {
    generate_button_id: "extras_generate",
    timeout_id: null,
    functions: {
      "modules.extras": {
        params: {
          extras_mode: 0,
          source_width: 0,
          source_height: 0,
          source_widths: [],
          source_heights: [],

          resize_mode: 0,
          scale_by: 2,
          scale_to_w: 512,
          scale_to_h: 512,
          scale_crop: false,

          upscaler_1_enabled: false,
          upscaler_2_enabled: false,
          upscaler_2_visibility: 0,

          gfpgan_enabled: false,
          gfpgan_visibility: 1,

          codeformer_enabled: false,
          codeformer_visibility: 1,

          caption_enabled: false,
          caption_option_number: 1,
        },
        link_params: {}, // tab_name: function_name
        mutipliers: {}, // multipler_name: value
        link_mutipliers: {}, // function_name: param_name
      },
    },
  }
}

async function updateButton(tabID, default_credit=1) {
  let credits = default_credit;
  if (systemMonitorState.hasOwnProperty(tabID) && systemMonitorState[tabID].generate_button_id) {
    let request_body = JSON.parse(JSON.stringify(systemMonitorState[tabID]));
    for (const functionName in request_body.functions) {
      for (const tabName in request_body.functions[functionName].link_params) {
        const linkedFunctionName = request_body.functions[functionName].link_params[tabName];
        if (systemMonitorState.hasOwnProperty(tabName) && systemMonitorState[tabName].functions.hasOwnProperty(linkedFunctionName)) {
          request_body.functions[functionName].params = {
            ...systemMonitorState[tabName].functions[linkedFunctionName].params,
            ...request_body.functions[functionName].params,
          };
        }
      }
      request_body.functions[functionName].link_params = {};
      for (const linkedMutiplierFunctionName in request_body.functions[functionName].link_mutipliers) {
        const linkedParamName = request_body.functions[functionName].link_mutipliers[linkedMutiplierFunctionName];
        if (request_body.functions.hasOwnProperty(linkedMutiplierFunctionName) &&
            request_body.functions[linkedMutiplierFunctionName].params.hasOwnProperty(linkedParamName)) {
          request_body.functions[functionName].mutipliers[linkedParamName] = request_body.functions[linkedMutiplierFunctionName].params[linkedParamName];
        }
      }
      request_body.functions[functionName].link_mutipliers = {};
      request_body.tab_id = tabID;
      delete request_body.timout_id;
    }
    try {
        const response = await fetch("/api/tasks/credits_consumption", {
            method: "POST",
            credentials: "include",
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(request_body)
        });
        if (!response.ok) {
            console.log(`HTTP error! status: ${response.status}`);
        } else {
            const response_json = await response.json();
            credits = response_json.inference;
        }
    } catch(e) {
        console.log(e);
    }
    const buttonEle = gradioApp().querySelector(`#${systemMonitorState[tabID].generate_button_id}`);
    const functionText = buttonEle.innerHTML.split("<span>")[0].trim();
    buttonEle.innerHTML = `${functionText} <span>(Estimated use ${credits} ${credits === 1 ? 'credit)': 'credits)'}</span>`;
  }
}

function monitorThisParam(
    tabID, functionName, paramName, extractor = null, params = {}, linkParams = {}, generateButtonId = null, multipliers = {}, linkMultipliers = {}) {
  let observe = async (...values) => {
    if (!systemMonitorState.hasOwnProperty(tabID)) {
      systemMonitorState[tabID] = {
        generate_button_id: generateButtonId,
        timeout_id: null,
        functions: {}
      }
    }
    if (!systemMonitorState[tabID].functions.hasOwnProperty(functionName)) {
      systemMonitorState[tabID].functions[functionName] = {
        params: params,
        link_params: linkParams,
        mutipliers: multipliers,
        link_mutipliers: linkMultipliers,
      };
    }
    if (typeof paramName === "string") {
      let value = values;
      if (value.length === 1) {
        value = value[0];
      }
      systemMonitorState[tabID].functions[functionName].params[paramName] = typeof extractor === "function"? extractor(value): value;
    } else if (Array.isArray(paramName)) {
      let final_values = values;
      if (typeof extractor === "function") {
        final_values = extractor(values);
      }
      if (Array.isArray(final_values) && final_values.length === paramName.length) {
        for (let i = 0; i < paramName.length; i++) {
          systemMonitorState[tabID].functions[functionName].params[paramName[i]] = final_values[i];
        }
      }
    }

    if (systemMonitorState[tabID].timeout_id !== null) {
      clearTimeout(systemMonitorState[tabID].timeout_id);
    }
    systemMonitorState[tabID].timeout_id = setTimeout(async () => {
      await updateButton(tabID);
      systemMonitorState[tabID].timeout_id = null;
    }, 1000);
    return values;
  }
  return observe;
}

function monitorMutiplier(
    tabID, functionName, multiplierName, extractor = null, linkParams = {}, generateButtonId = null, params = {}, multipliers = {}, linkMultipliers = {}) {
  let observe = async (...values) => {
    if (!systemMonitorState.hasOwnProperty(tabID)) {
      systemMonitorState[tabID] = {
        generate_button_id: generateButtonId,
        timeout_id: null,
        functions: {}
      };
    }
    if (!systemMonitorState[tabID].functions.hasOwnProperty(functionName)) {
      systemMonitorState[tabID].functions[functionName] = {
        params: params,
        link_params: linkParams,
        mutipliers: multipliers,
        link_mutipliers: linkMultipliers,
      };
    }
    if (typeof multiplierName === "string") {
      let value = values;
      if (value.length === 1) {
        value = value[0];
      }
      systemMonitorState[tabID].functions[functionName].mutipliers[multiplierName] = typeof extractor === "function"? extractor(value): value;
    } else if (Array.isArray(multiplierName)) {
      let final_values = values;
      if (typeof extractor === "function") {
        final_values = extractor(values);
      }
      if (Array.isArray(final_values) && final_values.length === multiplierName.length) {
        for (let i = 0; i < multiplierName.length; i++) {
          systemMonitorState[tabID].functions[functionName].mutipliers[multiplierName[i]] = final_values[i];
        }
      }
    }

    if (systemMonitorState[tabID].timeout_id !== null) {
      clearTimeout(systemMonitorState[tabID].timeout_id);
    }
    systemMonitorState[tabID].timeout_id = setTimeout(async () => {
      await updateButton(tabID);
      systemMonitorState[tabID].timeout_id = null;
    }, 1000);
    return values;
  }
  return observe;
}

function resetMutipliers(tabID, functionName, resetLinkParams = false, resetLinkMultipliers = false) {
  let observe = async (...values) => {
    if (systemMonitorState.hasOwnProperty(tabID) && systemMonitorState[tabID].functions.hasOwnProperty(functionName)) {
      systemMonitorState[tabID].functions[functionName].mutipliers = {};
      if (resetLinkParams) {
        systemMonitorState[tabID].functions[functionName].link_params = {};
      }
      if (resetLinkMultipliers) {
        systemMonitorState[tabID].functions[functionName].link_mutipliers = {};
      }
    }
    await updateButton(tabID);
    return values;
  }
  return observe;
}

onUiLoaded(async function(){
  await updateButton("tab_txt2img");
  await updateButton("tab_img2img");
  await updateButton("tab_extras", 0);
});
