const fetchPost = ({ data, url}) => {
    try {
        return fetch(url, {
            method: 'POST', 
            credentials: "include",
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        })
    } catch(e) {
        return new Promise.reject(e);
    }
}

const fetchDelete = (url, data = {}) => {
    try {
        return fetch(url, {
            method: 'DELETE', 
            credentials: "include",
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        })
    } catch(e) {
        return new Promise.reject(e);
    }
}

const fetchGet = (url) => {
    try {
        return fetch(url, {
            method: 'GET', 
            credentials: "include",
            cache: "no-cache"
        })
    } catch(e) {
        return new Promise.reject(e);
    }
}