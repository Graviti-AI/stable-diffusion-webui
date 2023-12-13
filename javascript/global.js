const PRICING_URL = 'https://www.diffus.graviti.com/pricing';
let galleryModelTotalPage = {
  personal: {
    checkpoints: 1,
    lora: 1,
    hypernetworks: 1,
    textual_inversion: 1,
  },
  public: {
    checkpoints: 1,
    lora: 1,
    hypernetworks: 1,
    textual_inversion: 1,
  },
  private: {
    checkpoints: 1,
    lora: 1,
    hypernetworks: 1,
    textual_inversion: 1,
  },
};
const model_type_mapper = {
  checkpoints: 'checkpoint',
  lora: 'lora',
  hypernetworks: 'hypernetwork',
  textual_inversion: 'embedding',
};
let currentModelTab = 'img2img';

let currentModelType = 'checkpoints';

const hasInitTabs = new Map();

let gallertModelCurrentPage = {
  checkpoints: 1,
  lora: 1,
  hypernetworks: 1,
  textual_inversion: 1,
};
let gallertModelScrollloads = [];
let personalTabs = '';
let publicTabs = '';
let gallerySearchBtn = null;
const defaultModelType = ['checkpoints', 'textual_inversion', 'hypernetworks', 'lora'];
let searchValue = '';
let tabSearchValueMap = new Map();
const isPcScreen = window.innerWidth > 600;
let userTier = 'Free';
let featurePermissions = null;
const tierLevels = {
  free: 0,
  basic: 1,
  plus: 2,
  pro: 3,
  api: 4,
};

let connectNewModelApi = true;
function testApi() {
  const promise = fetchGet(
    `/internal/favorite_models?model_type='checkpoint'&search_value=&page=1&page_size=1`
  );
  promise.then((state) => {
    if (state.status !== 200) {
      connectNewModelApi = false;
    }
  });
}

function judgeEnvironment() {
  const origin = location.origin;
  return (origin.includes('com') ||
    origin.includes('me') ||
    origin.includes('co')) &&
    !origin.includes('test')
    ? 'prod'
    : 'dev';
}

let channelResult = null;
let hasSingPermission = false;
let orderInfoResult = null;

function changeCreditsPackageLink() {
  if (["basic", "plus", "pro", "api"].includes(orderInfoResult.tier.toLowerCase())) {
    gtag("event", "conversion", {
        send_to: "AW-347751974/EiR7CPWfu88YEKaM6aUB",
        value: 12.0,
        currency: "USD",
    });
    const packageIcon = gradioApp().querySelector("#package");
    if (packageIcon) {
        packageIcon.style.display = "flex";
        const aLink = packageIcon.querySelector("a");
        const spanNode = aLink.querySelector("span");
        const resultInfo = { user_id: orderInfoResult.user_id };
        const referenceId = Base64.encodeURI(JSON.stringify(resultInfo));
        if (channelResult) {
          const {
            prices: { credit_package },
          } = channelResult;
          const host = credit_package.price_link;
          aLink.href = `${host}?prefilled_email=${orderInfoResult.email}&client_reference_id=${referenceId}`;
        }
        spanNode.textContent = isPcScreen ? "Credits Package" : "";
    }
  }
}

testApi();
