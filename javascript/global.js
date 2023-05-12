const PRICING_URL = 'https://www.diffus.graviti.com/pricing';
const galleryModelTotalPage = {
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

const currentModelType = {
    personal: 'checkpoints',
    public: 'checkpoints'
}


const gallertModelCurrentPage = {
    'checkpoints': 1,
    'lora': 1,
    'hypernetworks': 1,
    'textual_inversion': 1
};
const gallertModelScrollloads = [];
const defaultModelType = ['checkpoints', 'textual_inversion', 'hypernetworks', 'lora'];
