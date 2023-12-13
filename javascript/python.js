let PYTHON = {
    range: function* (s1, s2 = null, step = 1) {
        if (s2 === null) {
            s2 = s1;
            s1 = 0;
        }
        if (step > 0) {
            if (s1 >= s2) {
                return;
            }
            for (let i = s1; i < s2; i += step) {
                yield i;
            }
        } else if (step < 0) {
            if (s1 <= s2) {
                return;
            }
            for (let i = s1; i > s2; i += step) {
                yield i;
            }
        } else {
            throw "range() arg 3 must not be zero";
        }
    },

    reversed: function* (sequence) {
        for (let i = sequence.length - 1; i >= 0; --i) {
            yield sequence[i];
        }
    },

    zip: function* (...iterables) {
        let iterators = iterables.map((i) => i[Symbol.iterator]());
        while (true) {
            let results = iterators.map((iter) => iter.next());
            if (results.some((res) => res.done)) {
                return;
            } else {
                yield results.map((res) => res.value);
            }
        }
    },
};
