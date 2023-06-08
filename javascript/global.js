const PRICING_URL = 'https://www.diffus.graviti.com/pricing';
let galleryModelTotalPage = {
    personal: {
        'checkpoints': 1,
        'lora': 1,
        'hypernetworks': 1,
        'textual_inversion': 1
    },
    public: {
        'checkpoints': 1,
        'lora': 1,
        'hypernetworks': 1,
        'textual_inversion': 1
    },
    private: {
        'checkpoints': 1,
        'lora': 1,
        'hypernetworks': 1,
        'textual_inversion': 1
    }
}
const model_type_mapper = {
    'checkpoints': 'checkpoint',
    'lora': 'lora',
    'hypernetworks': 'hypernetwork',
    'textual_inversion': 'embedding',
}
let currentModelTab = 'txt2img';

let currentModelType = 'checkpoints';

const hasInitTabs = new Map();

let gallertModelCurrentPage = {
    'checkpoints': 1,
    'lora': 1,
    'hypernetworks': 1,
    'textual_inversion': 1
};
let gallertModelScrollloads = [];
let personalTabs = '';
let publicTabs = '';
let gallerySearchBtn = null;
const defaultModelType = ['checkpoints', 'textual_inversion', 'hypernetworks', 'lora'];
let searchValue = '';
let tabSearchValueMap = new Map();
