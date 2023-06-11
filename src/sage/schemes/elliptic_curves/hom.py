"""
Elliptic-curve morphisms

This class serves as a common parent for various specializations of
morphisms between elliptic curves, with the aim of providing a common
interface regardless of implementation details.

Current implementations of elliptic-curve morphisms (child classes):

- :class:`~sage.schemes.elliptic_curves.ell_curve_isogeny.EllipticCurveIsogeny`
- :class:`~sage.schemes.elliptic_curves.weierstrass_morphism.WeierstrassIsomorphism`
- :class:`~sage.schemes.elliptic_curves.hom_composite.EllipticCurveHom_composite`
- :class:`~sage.schemes.elliptic_curves.hom_scalar.EllipticCurveHom_scalar`
- :class:`~sage.schemes.elliptic_curves.hom_frobenius.EllipticCurveHom_frobenius`
- :class:`~sage.schemes.elliptic_curves.hom_velusqrt.EllipticCurveHom_velusqrt`

AUTHORS:

- See authors of :class:`EllipticCurveIsogeny`. Some of the code
  in this class was lifted from there.

- Lorenz Panny (2021): Refactor isogenies and isomorphisms into
  the common :class:`EllipticCurveHom` interface.

- Lorenz Panny (2022): :meth:`~EllipticCurveHom.matrix_on_subgroup`
"""
from sage.misc.cachefunc import cached_method
from sage.structure.richcmp import richcmp_not_equal, richcmp, op_EQ, op_NE

from sage.categories.morphism import Morphism

from sage.arith.misc import integer_floor

from sage.rings.finite_rings import finite_field_base
from sage.rings.number_field import number_field_base

import sage.schemes.elliptic_curves.weierstrass_morphism as wm


class EllipticCurveHom(Morphism):
    """
    Base class for elliptic-curve morphisms.
    """
    def __init__(self, *args, **kwds):
        r"""
        Constructor for elliptic-curve morphisms.

        EXAMPLES::

            sage: E = EllipticCurve(GF(257^2), [5,5])
            sage: P = E.lift_x(1)
            sage: E.isogeny(P)                        # indirect doctest
            Isogeny of degree 127 from Elliptic Curve defined by y^2 = x^3 + 5*x + 5 over Finite Field in z2 of size 257^2 to Elliptic Curve defined by y^2 = x^3 + 151*x + 22 over Finite Field in z2 of size 257^2
            sage: E.isogeny(P, algorithm='factored')  # indirect doctest
            Composite morphism of degree 127 = 127:
              From: Elliptic Curve defined by y^2 = x^3 + 5*x + 5 over Finite Field in z2 of size 257^2
              To:   Elliptic Curve defined by y^2 = x^3 + 151*x + 22 over Finite Field in z2 of size 257^2
            sage: E.isogeny(P, algorithm='velusqrt')  # indirect doctest
            Elliptic-curve isogeny (using square-root Vélu) of degree 127:
              From: Elliptic Curve defined by y^2 = x^3 + 5*x + 5 over Finite Field in z2 of size 257^2
              To:   Elliptic Curve defined by y^2 = x^3 + 119*x + 231 over Finite Field in z2 of size 257^2
            sage: E.montgomery_model(morphism=True)   # indirect doctest
            (Elliptic Curve defined by y^2 = x^3 + (199*z2+73)*x^2 + x over Finite Field in z2 of size 257^2,
             Elliptic-curve morphism:
               From: Elliptic Curve defined by y^2 = x^3 + 5*x + 5 over Finite Field in z2 of size 257^2
               To:   Elliptic Curve defined by y^2 = x^3 + (199*z2+73)*x^2 + x over Finite Field in z2 of size 257^2
               Via:  (u,r,s,t) = (88*z2 + 253, 208*z2 + 90, 0, 0))
        """
        super().__init__(*args, **kwds)

        # Over finite fields, isogenous curves have the same number of
        # rational points, hence we copy over the cached curve orders.
        if isinstance(self.base_ring(), finite_field_base.FiniteField) and self.degree():
            self._codomain._fetch_cached_order(self._domain)
            self._domain._fetch_cached_order(self._codomain)

    def _repr_type(self):
        r"""
        Return a textual representation of what kind of morphism
        this is. Used by :meth:`Morphism._repr_`.

        TESTS::

            sage: from sage.schemes.elliptic_curves.hom import EllipticCurveHom
            sage: EllipticCurveHom._repr_type(None)
            'Elliptic-curve'
        """
        return 'Elliptic-curve'

    @staticmethod
    def _composition_impl(left, right):
        r"""
        Called by :meth:`_composition_`.

        TESTS::

            sage: from sage.schemes.elliptic_curves.hom import EllipticCurveHom
            sage: EllipticCurveHom._composition_impl(None, None)
            NotImplemented
        """
        return NotImplemented

    def _composition_(self, other, homset):
        r"""
        Return the composition of this elliptic-curve morphism
        with another elliptic-curve morphism.

        EXAMPLES::

            sage: E = EllipticCurve(GF(19), [1,0])
            sage: phi = E.isogeny(E(0,0))
            sage: iso = E.change_weierstrass_model(5,0,0,0).isomorphism_to(E)
            sage: phi * iso
            Isogeny of degree 2 from Elliptic Curve defined by y^2 = x^3 + 9*x over Finite Field of size 19 to Elliptic Curve defined by y^2 = x^3 + 15*x over Finite Field of size 19
            sage: phi.dual() * phi
            Composite morphism of degree 4 = 2^2:
              From: Elliptic Curve defined by y^2 = x^3 + x over Finite Field of size 19
              To:   Elliptic Curve defined by y^2 = x^3 + x over Finite Field of size 19
        """
        if not isinstance(self, EllipticCurveHom) or not isinstance(other, EllipticCurveHom):
            raise TypeError(f'cannot compose {type(self)} with {type(other)}')

        ret = self._composition_impl(self, other)
        if ret is not NotImplemented:
            return ret

        ret = other._composition_impl(self, other)
        if ret is not NotImplemented:
            return ret

        from sage.schemes.elliptic_curves.hom_composite import EllipticCurveHom_composite
        return EllipticCurveHom_composite.from_factors([other, self])

    @staticmethod
    def _comparison_impl(left, right, op):
        r"""
        Called by :meth:`_richcmp_`.

        TESTS::

            sage: from sage.schemes.elliptic_curves.hom import EllipticCurveHom
            sage: EllipticCurveHom._comparison_impl(None, None, None)
            NotImplemented
        """
        return NotImplemented

    def _richcmp_(self, other, op):
        r"""
        Compare :class:`EllipticCurveHom` objects.

        ALGORITHM:

        The method first makes sure that domain, codomain and degree match.
        Then, it determines if there is a specialized comparison method by
        trying :meth:`_comparison_impl` on either input. If not, it falls
        back to comparing :meth:`rational_maps`.

        EXAMPLES::

            sage: E = EllipticCurve(QQ, [0,0,0,1,0])
            sage: phi_v = EllipticCurveIsogeny(E, E((0,0)))
            sage: phi_k = EllipticCurveIsogeny(E, [0,1])
            sage: phi_k == phi_v
            True
            sage: E_F17 = EllipticCurve(GF(17), [0,0,0,1,0])
            sage: phi_p = EllipticCurveIsogeny(E_F17, [0,1])
            sage: phi_p == phi_v
            False
            sage: E = EllipticCurve('11a1')
            sage: phi = E.isogeny(E(5,5))
            sage: phi == phi
            True
            sage: phi == -phi
            False
            sage: psi = E.isogeny(phi.kernel_polynomial())
            sage: phi == psi
            True
            sage: phi.dual() == psi.dual()
            True

        ::

            sage: from sage.schemes.elliptic_curves.weierstrass_morphism import WeierstrassIsomorphism, identity_morphism
            sage: E = EllipticCurve([9,9])
            sage: F = E.change_ring(GF(71))
            sage: wE = identity_morphism(E)
            sage: wF = identity_morphism(F)
            sage: mE = E.scalar_multiplication(1)
            sage: mF = F.multiplication_by_m_isogeny(1)
            doctest:warning ... DeprecationWarning: ...
            sage: [mE == wE, mF == wF]
            [True, True]
            sage: [a == b for a in (wE,mE) for b in (wF,mF)]
            [False, False, False, False]

        .. SEEALSO::

            - :meth:`_comparison_impl`
            - :func:`compare_via_evaluation`
        """
        if not isinstance(self, EllipticCurveHom) or not isinstance(other, EllipticCurveHom):
            raise TypeError(f'cannot compare {type(self)} to {type(other)}')

        if op == op_NE:
            return not self._richcmp_(other, op_EQ)

        # We first compare domain, codomain, and degree; cf. Issue #11327

        lx, rx = self.domain(), other.domain()
        if lx != rx:
            return richcmp_not_equal(lx, rx, op)

        lx, rx = self.codomain(), other.codomain()
        if lx != rx:
            return richcmp_not_equal(lx, rx, op)

        lx, rx = self.degree(), other.degree()
        if lx != rx:
            return richcmp_not_equal(lx, rx, op)

        # Do self or other have specialized comparison methods?

        ret = self._comparison_impl(self, other, op)
        if ret is not NotImplemented:
            return ret

        ret = other._comparison_impl(self, other, op)
        if ret is not NotImplemented:
            return ret

        # If not, fall back to comparing rational maps; cf. Issue #11327

        return richcmp(self.rational_maps(), other.rational_maps(), op)

    def degree(self):
        r"""
        Return the degree of this elliptic-curve morphism.

        EXAMPLES::

            sage: E = EllipticCurve(QQ, [0,0,0,1,0])
            sage: phi = EllipticCurveIsogeny(E, E((0,0)))
            sage: phi.degree()
            2
            sage: phi = EllipticCurveIsogeny(E, [0,1,0,1])
            sage: phi.degree()
            4

            sage: E = EllipticCurve(GF(31), [1,0,0,1,2])
            sage: phi = EllipticCurveIsogeny(E, [17, 1])
            sage: phi.degree()
            3

        Degrees are multiplicative, so the degree of a composite isogeny
        is the product of the degrees of the individual factors::

            sage: from sage.schemes.elliptic_curves.hom_composite import EllipticCurveHom_composite
            sage: E = EllipticCurve(GF(419), [1,0])
            sage: P, = E.gens()
            sage: phi = EllipticCurveHom_composite(E, P+P)
            sage: phi.degree()
            210
            sage: phi.degree() == prod(f.degree() for f in phi.factors())
            True

        Isomorphisms always have degree `1` by definition::

            sage: E1 = EllipticCurve([1,2,3,4,5])
            sage: E2 = EllipticCurve_from_j(E1.j_invariant())
            sage: E1.isomorphism_to(E2).degree()
            1

        TESTS::

            sage: from sage.schemes.elliptic_curves.hom import EllipticCurveHom
            sage: EllipticCurveHom.degree(None)
            Traceback (most recent call last):
            ...
            NotImplementedError: ...
        """
        try:
            return self._degree
        except AttributeError:
            raise NotImplementedError('children must implement')

    def kernel_polynomial(self):
        r"""
        Return the kernel polynomial of this elliptic-curve morphism.

        Implemented by child classes. For examples, see:

        - :meth:`EllipticCurveIsogeny.kernel_polynomial`
        - :meth:`sage.schemes.elliptic_curves.weierstrass_morphism.WeierstrassIsomorphism.kernel_polynomial`
        - :meth:`sage.schemes.elliptic_curves.hom_composite.EllipticCurveHom_composite.kernel_polynomial`
        - :meth:`sage.schemes.elliptic_curves.hom_scalar.EllipticCurveHom_scalar.kernel_polynomial`
        - :meth:`sage.schemes.elliptic_curves.hom_frobenius.EllipticCurveHom_frobenius.kernel_polynomial`

        TESTS::

            sage: from sage.schemes.elliptic_curves.hom import EllipticCurveHom
            sage: EllipticCurveHom.kernel_polynomial(None)
            Traceback (most recent call last):
            ...
            NotImplementedError: ...
        """
        raise NotImplementedError('children must implement')

    def dual(self):
        r"""
        Return the dual of this elliptic-curve morphism.

        Implemented by child classes. For examples, see:

        - :meth:`EllipticCurveIsogeny.dual`
        - :meth:`sage.schemes.elliptic_curves.weierstrass_morphism.WeierstrassIsomorphism.dual`
        - :meth:`sage.schemes.elliptic_curves.hom_composite.EllipticCurveHom_composite.dual`
        - :meth:`sage.schemes.elliptic_curves.hom_scalar.EllipticCurveHom_scalar.dual`
        - :meth:`sage.schemes.elliptic_curves.hom_frobenius.EllipticCurveHom_frobenius.dual`

        TESTS::

            sage: from sage.schemes.elliptic_curves.hom import EllipticCurveHom
            sage: EllipticCurveHom.dual(None)
            Traceback (most recent call last):
            ...
            NotImplementedError: ...
        """
        raise NotImplementedError('children must implement')

    def rational_maps(self):
        r"""
        Return the pair of explicit rational maps defining this
        elliptic-curve morphism as fractions of bivariate
        polynomials in `x` and `y`.

        Implemented by child classes. For examples, see:

        - :meth:`EllipticCurveIsogeny.rational_maps`
        - :meth:`sage.schemes.elliptic_curves.weierstrass_morphism.WeierstrassIsomorphism.rational_maps`
        - :meth:`sage.schemes.elliptic_curves.hom_composite.EllipticCurveHom_composite.rational_maps`
        - :meth:`sage.schemes.elliptic_curves.hom_scalar.EllipticCurveHom_scalar.rational_maps`
        - :meth:`sage.schemes.elliptic_curves.hom_frobenius.EllipticCurveHom_frobenius.rational_maps`

        TESTS::

            sage: from sage.schemes.elliptic_curves.hom import EllipticCurveHom
            sage: EllipticCurveHom.rational_maps(None)
            Traceback (most recent call last):
            ...
            NotImplementedError: ...
        """
        raise NotImplementedError('children must implement')

    def x_rational_map(self):
        r"""
        Return the `x`-coordinate rational map of this elliptic-curve
        morphism as a univariate rational expression in `x`.

        Implemented by child classes. For examples, see:

        - :meth:`EllipticCurveIsogeny.x_rational_map`
        - :meth:`sage.schemes.elliptic_curves.weierstrass_morphism.WeierstrassIsomorphism.x_rational_map`
        - :meth:`sage.schemes.elliptic_curves.hom_composite.EllipticCurveHom_composite.x_rational_map`
        - :meth:`sage.schemes.elliptic_curves.hom_scalar.EllipticCurveHom_scalar.x_rational_map`
        - :meth:`sage.schemes.elliptic_curves.hom_frobenius.EllipticCurveHom_frobenius.x_rational_map`

        TESTS::

            sage: from sage.schemes.elliptic_curves.hom import EllipticCurveHom
            sage: EllipticCurveHom.x_rational_map(None)
            Traceback (most recent call last):
            ...
            NotImplementedError: ...
        """
        # TODO: could have a default implementation that simply
        # returns the first component of rational_maps()
        raise NotImplementedError('children must implement')

    def scaling_factor(self):
        r"""
        Return the Weierstrass scaling factor associated to this
        elliptic-curve morphism.

        The scaling factor is the constant `u` (in the base field)
        such that `\varphi^* \omega_2 = u \omega_1`, where
        `\varphi: E_1\to E_2` is this morphism and `\omega_i` are
        the standard Weierstrass differentials on `E_i` defined by
        `\mathrm dx/(2y+a_1x+a_3)`.

        Implemented by child classes. For examples, see:

        - :meth:`EllipticCurveIsogeny.scaling_factor`
        - :meth:`sage.schemes.elliptic_curves.weierstrass_morphism.WeierstrassIsomorphism.scaling_factor`
        - :meth:`sage.schemes.elliptic_curves.hom_composite.EllipticCurveHom_composite.scaling_factor`
        - :meth:`sage.schemes.elliptic_curves.hom_scalar.EllipticCurveHom_scalar.scaling_factor`

        TESTS::

            sage: from sage.schemes.elliptic_curves.hom import EllipticCurveHom
            sage: EllipticCurveHom.scaling_factor(None)
            Traceback (most recent call last):
            ...
            NotImplementedError: ...
        """
        # TODO: could have a default implementation that simply
        #       returns .formal()[1], but it seems safer to fail
        #       visibly to make sure we would notice regressions
        raise NotImplementedError('children must implement')

    def formal(self, prec=20):
        r"""
        Return the formal isogeny associated to this elliptic-curve
        morphism as a power series in the variable `t=-x/y` on the
        domain curve.

        INPUT:

        - ``prec`` -- (default: 20), the precision with which the
          computations in the formal group are carried out.

        EXAMPLES::

            sage: E = EllipticCurve(GF(13),[1,7])
            sage: phi = E.isogeny(E(10,4))
            sage: phi.formal()
            t + 12*t^13 + 2*t^17 + 8*t^19 + 2*t^21 + O(t^23)

        ::

            sage: E = EllipticCurve([0,1])
            sage: phi = E.isogeny(E(2,3))
            sage: phi.formal(prec=10)
            t + 54*t^5 + 255*t^7 + 2430*t^9 + 19278*t^11 + O(t^13)

        ::

            sage: E = EllipticCurve('11a2')
            sage: R.<x> = QQ[]
            sage: phi = E.isogeny(x^2 + 101*x + 12751/5)
            sage: phi.formal(prec=7)
            t - 2724/5*t^5 + 209046/5*t^7 - 4767/5*t^8 + 29200946/5*t^9 + O(t^10)
        """
        Eh = self._domain.formal()
        f, g = self.rational_maps()
        xh = Eh.x(prec=prec)
        assert not self.is_separable() or xh.valuation() == -2, f"xh has valuation {xh.valuation()} (should be -2)"
        yh = Eh.y(prec=prec)
        assert not self.is_separable() or yh.valuation() == -3, f"yh has valuation {yh.valuation()} (should be -3)"
        fh = f(xh,yh)
        assert not self.is_separable() or fh.valuation() == -2, f"fh has valuation {fh.valuation()} (should be -2)"
        gh = g(xh,yh)
        assert not self.is_separable() or gh.valuation() == -3, f"gh has valuation {gh.valuation()} (should be -3)"
        th = -fh/gh
        assert not self.is_separable() or th.valuation() == +1, f"th has valuation {th.valuation()} (should be +1)"
        return th

    def is_normalized(self):
        r"""
        Determine whether this morphism is a normalized isogeny.

        .. NOTE::

            An isogeny `\varphi\colon E_1\to E_2` between two given
            Weierstrass equations is said to be *normalized* if the
            `\varphi^*(\omega_2) = \omega_1`, where `\omega_1` and
            `\omega_2` are the invariant differentials on `E_1` and
            `E_2` corresponding to the given equation.

        EXAMPLES::

            sage: from sage.schemes.elliptic_curves.weierstrass_morphism import WeierstrassIsomorphism
            sage: E = EllipticCurve(GF(7), [0,0,0,1,0])
            sage: R.<x> = GF(7)[]
            sage: phi = EllipticCurveIsogeny(E, x)
            sage: phi.is_normalized()
            True
            sage: isom = WeierstrassIsomorphism(phi.codomain(), (3, 0, 0, 0))
            sage: phi = isom * phi
            sage: phi.is_normalized()
            False
            sage: isom = WeierstrassIsomorphism(phi.codomain(), (5, 0, 0, 0))
            sage: phi = isom * phi
            sage: phi.is_normalized()
            True
            sage: isom = WeierstrassIsomorphism(phi.codomain(), (1, 1, 1, 1))
            sage: phi = isom * phi
            sage: phi.is_normalized()
            True

        ::

            sage: F = GF(2^5, 'alpha'); alpha = F.gen()
            sage: E = EllipticCurve(F, [1,0,1,1,1])
            sage: R.<x> = F[]
            sage: phi = EllipticCurveIsogeny(E, x+1)
            sage: isom = WeierstrassIsomorphism(phi.codomain(), (alpha, 0, 0, 0))
            sage: phi.is_normalized()
            True
            sage: phi = isom * phi
            sage: phi.is_normalized()
            False
            sage: isom = WeierstrassIsomorphism(phi.codomain(), (1/alpha, 0, 0, 0))
            sage: phi = isom * phi
            sage: phi.is_normalized()
            True
            sage: isom = WeierstrassIsomorphism(phi.codomain(), (1, 1, 1, 1))
            sage: phi = isom * phi
            sage: phi.is_normalized()
            True

        ::

            sage: E = EllipticCurve('11a1')
            sage: R.<x> = QQ[]
            sage: f = x^3 - x^2 - 10*x - 79/4
            sage: phi = EllipticCurveIsogeny(E, f)
            sage: isom = WeierstrassIsomorphism(phi.codomain(), (2, 0, 0, 0))
            sage: phi.is_normalized()
            True
            sage: phi = isom * phi
            sage: phi.is_normalized()
            False
            sage: isom = WeierstrassIsomorphism(phi.codomain(), (1/2, 0, 0, 0))
            sage: phi = isom * phi
            sage: phi.is_normalized()
            True
            sage: isom = WeierstrassIsomorphism(phi.codomain(), (1, 1, 1, 1))
            sage: phi = isom * phi
            sage: phi.is_normalized()
            True

        ALGORITHM: We check if :meth:`scaling_factor` returns `1`.
        """
        return self.scaling_factor() == 1

    def is_separable(self):
        r"""
        Determine whether or not this morphism is separable.

        Implemented by child classes. For examples, see:

        - :meth:`EllipticCurveIsogeny.is_separable`
        - :meth:`sage.schemes.elliptic_curves.weierstrass_morphism.WeierstrassIsomorphism.is_separable`
        - :meth:`sage.schemes.elliptic_curves.hom_composite.EllipticCurveHom_composite.is_separable`
        - :meth:`sage.schemes.elliptic_curves.hom_scalar.EllipticCurveHom_scalar.is_separable`
        - :meth:`sage.schemes.elliptic_curves.hom_frobenius.EllipticCurveHom_frobenius.is_separable`

        TESTS::

            sage: from sage.schemes.elliptic_curves.hom import EllipticCurveHom
            sage: EllipticCurveHom.is_separable(None)
            Traceback (most recent call last):
            ...
            NotImplementedError: ...
        """
        raise NotImplementedError('children must implement')

    def is_surjective(self):
        r"""
        Determine whether or not this morphism is surjective.

        .. NOTE::

            This method currently always returns ``True``, since a
            non-constant map of algebraic curves must be surjective,
            and Sage does not yet implement the constant zero map.
            This will probably change in the future.

        EXAMPLES::

            sage: E = EllipticCurve('11a1')
            sage: R.<x> = QQ[]
            sage: f = x^2 + x - 29/5
            sage: phi = EllipticCurveIsogeny(E, f)
            sage: phi.is_surjective()
            True

        ::

            sage: E = EllipticCurve(GF(7), [0,0,0,1,0])
            sage: phi = EllipticCurveIsogeny(E,  E((0,0)))
            sage: phi.is_surjective()
            True

        ::

            sage: F = GF(2^5, 'omega')
            sage: E = EllipticCurve(j=F(0))
            sage: R.<x> = F[]
            sage: phi = EllipticCurveIsogeny(E, x)
            sage: phi.is_surjective()
            True
        """
        return bool(self.degree())

    def is_injective(self):
        r"""
        Determine whether or not this morphism has trivial kernel.

        EXAMPLES::

            sage: E = EllipticCurve('11a1')
            sage: R.<x> = QQ[]
            sage: f = x^2 + x - 29/5
            sage: phi = EllipticCurveIsogeny(E, f)
            sage: phi.is_injective()
            False
            sage: phi = EllipticCurveIsogeny(E, R(1))
            sage: phi.is_injective()
            True

        ::

            sage: F = GF(7)
            sage: E = EllipticCurve(j=F(0))
            sage: phi = EllipticCurveIsogeny(E, [ E((0,-1)), E((0,1))])
            sage: phi.is_injective()
            False
            sage: phi = EllipticCurveIsogeny(E, E(0))
            sage: phi.is_injective()
            True
        """
        if not self.is_separable():
            # TODO: should implement .separable_degree() or similar
            raise NotImplementedError
        return self.degree() == 1

    def is_zero(self):
        r"""
        Check whether this elliptic-curve morphism is the zero map.

        .. NOTE::

            This function currently always returns ``True`` as Sage
            does not yet implement the constant zero morphism. This
            will probably change in the future.

        EXAMPLES::

            sage: E = EllipticCurve(j=GF(7)(0))
            sage: phi = EllipticCurveIsogeny(E, [E(0,1), E(0,-1)])
            sage: phi.is_zero()
            False
        """
        return not self.degree()

    def __neg__(self):
        r"""
        Return the negative of this elliptic-curve morphism. In other
        words, return `[-1]\circ\varphi` where `\varphi` is ``self``
        and `[-1]` is the negation automorphism on the codomain curve.

        EXAMPLES::

            sage: from sage.schemes.elliptic_curves.hom import EllipticCurveHom
            sage: E = EllipticCurve(GF(1019), [5,5])
            sage: phi = E.isogeny(E.lift_x(73))
            sage: f,g = phi.rational_maps()
            sage: psi = EllipticCurveHom.__neg__(phi)
            sage: psi.rational_maps() == (f, -g)
            True
        """
        return wm.negation_morphism(self.codomain()) * self

    @cached_method
    def __hash__(self):
        r"""
        Return a hash value for this elliptic-curve morphism.

        ALGORITHM:

        Hash a tuple containing the domain, codomain, and kernel
        polynomial of this morphism. (The base field is factored
        into the computation as part of the (co)domain hashes.)

        EXAMPLES::

            sage: E = EllipticCurve(QQ, [0,0,0,1,0])
            sage: phi_v = EllipticCurveIsogeny(E, E((0,0)))
            sage: phi_k = EllipticCurveIsogeny(E, [0,1])
            sage: phi_k.__hash__() == phi_v.__hash__()
            True
            sage: E_F17 = EllipticCurve(GF(17), [0,0,0,1,1])
            sage: phi_p = EllipticCurveIsogeny(E_F17, E_F17([0,1]))
            sage: phi_p.__hash__() == phi_v.__hash__()
            False

        ::

            sage: E = EllipticCurve('49a3')
            sage: R.<X> = QQ[]
            sage: EllipticCurveIsogeny(E,X^3-13*X^2-58*X+503,check=False)
            Isogeny of degree 7 from Elliptic Curve defined by y^2 + x*y = x^3 - x^2 - 107*x + 552 over Rational Field to Elliptic Curve defined by y^2 + x*y = x^3 - x^2 - 5252*x - 178837 over Rational Field
        """
        return hash((self.domain(), self.codomain(), self.kernel_polynomial()))

    def as_morphism(self):
        r"""
        Return ``self`` as a morphism of projective schemes.

        EXAMPLES::

            sage: k = GF(11)
            sage: E = EllipticCurve(k, [1,1])
            sage: Q = E(6,5)
            sage: phi = E.isogeny(Q)
            sage: mor = phi.as_morphism()
            sage: mor.domain() == E
            True
            sage: mor.codomain() == phi.codomain()
            True
            sage: mor(Q) == phi(Q)
            True

        TESTS::

            sage: mor(0*Q)
            (0 : 1 : 0)
            sage: mor(1*Q)
            (0 : 1 : 0)
        """
        from sage.schemes.curves.constructor import Curve
        X_affine = Curve(self.domain()).affine_patch(2)
        Y_affine = Curve(self.codomain()).affine_patch(2)
        return X_affine.hom(self.rational_maps(), Y_affine).homogenize(2)

    def matrix_on_subgroup(self, domain_gens, codomain_gens=None):
        r"""
        Return the matrix by which this isogeny acts on the
        `n`-torsion subgroup with respect to the given bases.

        INPUT:

        - ``domain_gens`` -- basis `(P,Q)` of some `n`-torsion
          subgroup on the domain of this elliptic-curve morphism

        - ``codomain_gens`` -- basis `(R,S)` of the `n`-torsion
          on the codomain of this morphism, or (default) ``None``
          if ``self`` is an endomorphism

        OUTPUT:

        A `2\times 2` matrix `M` over `\ZZ/n`, such that the
        image of any point `[a]P + [b]Q` under this morphism
        equals `[c]R + [d]S` where `(c\ d)^T = (a\ b) M`.

        EXAMPLES::

            sage: F.<i> = GF(419^2, modulus=[1,0,1])
            sage: E = EllipticCurve(F, [1,0])
            sage: P = E(3, 176*i)
            sage: Q = E(i+7, 67*i+48)
            sage: P.weil_pairing(Q, 420).multiplicative_order()
            420
            sage: iota = E.automorphisms()[2]; iota
            Elliptic-curve endomorphism of Elliptic Curve defined by y^2 = x^3 + x over Finite Field in i of size 419^2
              Via:  (u,r,s,t) = (i, 0, 0, 0)
            sage: iota^2 == E.scalar_multiplication(-1)
            True
            sage: mat = iota.matrix_on_subgroup((P,Q)); mat
            [301 386]
            [ 83 119]
            sage: mat.parent()
            Full MatrixSpace of 2 by 2 dense matrices over Ring of integers modulo 420
            sage: iota(P) == 301*P + 386*Q
            True
            sage: iota(Q) == 83*P + 119*Q
            True
            sage: a,b = 123, 456
            sage: c,d = vector((a,b)) * mat; (c,d)
            (111, 102)
            sage: iota(a*P + b*Q) == c*P + d*Q
            True

        One important application of this is to compute generators of
        the kernel subgroup of an isogeny, when the `n`-torsion subgroup
        containing the kernel is accessible::

            sage: K = E(83*i-16, 9*i-147)
            sage: K.order()
            7
            sage: phi = E.isogeny(K)
            sage: R,S = phi.codomain().gens()
            sage: mat = phi.matrix_on_subgroup((P,Q), (R,S))
            sage: mat  # random -- depends on R,S
            [124 263]
            [115 141]
            sage: kermat = mat.left_kernel_matrix(); kermat
            [300  60]
            sage: ker = [ZZ(v[0])*P + ZZ(v[1])*Q for v in kermat]
            sage: {phi(T) for T in ker}
            {(0 : 1 : 0)}
            sage: phi == E.isogeny(ker)
            True

        We can also compute the matrix of a Frobenius endomorphism
        (:class:`~sage.schemes.elliptic_curves.hom_frobenius.EllipticCurveHom_frobenius`)
        on a large enough subgroup to verify point-counting results::

            sage: F.<a> = GF((101, 36))
            sage: E = EllipticCurve(GF(101), [1,1])
            sage: EE = E.change_ring(F)
            sage: P,Q = EE.torsion_basis(37)
            sage: pi = EE.frobenius_isogeny()
            sage: M = pi.matrix_on_subgroup((P,Q))
            sage: M.parent()
            Full MatrixSpace of 2 by 2 dense matrices over Ring of integers modulo 37
            sage: M.trace()
            34
            sage: E.trace_of_frobenius()
            -3

        .. SEEALSO::

            To compute a basis of the `n`-torsion, you may use
            :meth:`~sage.schemes.elliptic_curves.ell_finite_field.EllipticCurve_finite_field.torsion_basis`.
        """
        if codomain_gens is None:
            if not self.is_endomorphism():
                raise ValueError('basis of codomain subgroup is required for non-endomorphisms')
            codomain_gens = domain_gens

        P,Q = domain_gens
        R,S = codomain_gens

        ords = {P.order() for P in (P,Q,R,S)}
        if len(ords) != 1:
            #TODO: Is there some meaningful way to lift this restriction?
            raise ValueError('generator points must all have the same order')
        n, = ords

        if P.weil_pairing(Q, n).multiplicative_order() != n:
            raise ValueError('generator points on domain are not independent')
        if R.weil_pairing(S, n).multiplicative_order() != n:
            raise ValueError('generator points on codomain are not independent')

        imP = self(P)
        imQ = self(Q)

        from sage.groups.additive_abelian.additive_abelian_wrapper import AdditiveAbelianGroupWrapper
        H = AdditiveAbelianGroupWrapper(self.codomain().point_homset(), [R,S], [n,n])
        vecP = H.discrete_log(imP)
        vecQ = H.discrete_log(imQ)

        from sage.matrix.constructor import matrix
        from sage.rings.finite_rings.integer_mod_ring import Zmod
        return matrix(Zmod(n), [vecP, vecQ])


def compare_via_evaluation(left, right):
    r"""
    Test if two elliptic-curve morphisms are equal by evaluating
    them at enough points.

    INPUT:

    - ``left``, ``right`` -- :class:`EllipticCurveHom` objects

    ALGORITHM:

    We use the fact that two isogenies of equal degree `d` must be
    the same if and only if they behave identically on more than
    `4d` points. (It suffices to check this on a few points that
    generate a large enough subgroup.)

    If the domain curve does not have sufficiently many rational
    points, the base field is extended first: Taking an extension
    of degree `O(\log(d))` suffices.

    EXAMPLES::

        sage: E = EllipticCurve(GF(83), [1,0])
        sage: phi = E.isogeny(12*E.0, model='montgomery'); phi
        Isogeny of degree 7 from Elliptic Curve defined by y^2 = x^3 + x over Finite Field of size 83 to Elliptic Curve defined by y^2 = x^3 + 70*x^2 + x over Finite Field of size 83
        sage: psi = phi.dual(); psi
        Isogeny of degree 7 from Elliptic Curve defined by y^2 = x^3 + 70*x^2 + x over Finite Field of size 83 to Elliptic Curve defined by y^2 = x^3 + x over Finite Field of size 83
        sage: from sage.schemes.elliptic_curves.hom_composite import EllipticCurveHom_composite
        sage: mu = EllipticCurveHom_composite.from_factors([phi, psi])
        sage: from sage.schemes.elliptic_curves.hom import compare_via_evaluation
        sage: compare_via_evaluation(mu, E.scalar_multiplication(7))
        True

    .. SEEALSO::

        - :meth:`sage.schemes.elliptic_curves.hom_composite.EllipticCurveHom_composite._richcmp_`
    """
    if left.domain() != right.domain():
        return False
    if left.codomain() != right.codomain():
        return False
    if left.degree() != right.degree():
        return False

    E = left.domain()
    F = E.base_ring()

    if isinstance(F, finite_field_base.FiniteField):
        q = F.cardinality()
        d = left.degree()
        e = integer_floor(1 + 2 * (2*d.sqrt() + 1).log(q))  # from Hasse bound
        e = next(i for i, n in enumerate(E.count_points(e+1), 1) if n > 4*d)
        EE = E.base_extend(F.extension(e, 'U'))  # named extension is faster
        Ps = EE.gens()
        return all(left._eval(P) == right._eval(P) for P in Ps)
    elif isinstance(F, number_field_base.NumberField):
        for _ in range(100):
            P = E.lift_x(F.random_element(), extend=True)
            if not P.has_finite_order():
                return left._eval(P) == right._eval(P)
        else:
            assert False, "couldn't find a point of infinite order"
    else:
        raise NotImplementedError('not implemented for this base field')


def find_post_isomorphism(phi, psi):
    r"""
    Given two isogenies `\phi: E\to E'` and `\psi: E\to E''`
    which are equal up to post-isomorphism defined over the
    same field, find that isomorphism.

    In other words, this function computes an isomorphism
    `\alpha: E'\to E''` such that `\alpha\circ\phi = \psi`.

    ALGORITHM:

    Start with a list of all isomorphisms `E'\to E''`. Then
    repeatedly evaluate `\phi` and `\psi` at random points
    `P` to filter the list for isomorphisms `\alpha` with
    `\alpha(\phi(P)) = \psi(P)`. Once only one candidate is
    left, return it. Periodically extend the base field to
    avoid getting stuck (say, if all candidate isomorphisms
    act the same on all rational points).

    EXAMPLES::

        sage: from sage.schemes.elliptic_curves.hom import find_post_isomorphism
        sage: E = EllipticCurve(GF(7^2), [1,0])
        sage: f = E.scalar_multiplication(1)
        sage: g = choice(E.automorphisms())
        sage: find_post_isomorphism(f, g) == g
        True

    ::

        sage: from sage.schemes.elliptic_curves.weierstrass_morphism import WeierstrassIsomorphism
        sage: from sage.schemes.elliptic_curves.hom_composite import EllipticCurveHom_composite
        sage: x = polygen(ZZ, 'x')
        sage: F.<i> = GF(883^2, modulus=x^2+1)
        sage: E = EllipticCurve(F, [1,0])
        sage: P = E.lift_x(117)
        sage: Q = E.lift_x(774)
        sage: w = WeierstrassIsomorphism(E, [i,0,0,0])
        sage: phi = EllipticCurveHom_composite(E, [P,w(Q)]) * w
        sage: psi = EllipticCurveHom_composite(E, [Q,w(P)])
        sage: phi.kernel_polynomial() == psi.kernel_polynomial()
        True
        sage: find_post_isomorphism(phi, psi)
        Elliptic-curve morphism:
          From: Elliptic Curve defined by y^2 = x^3 + 320*x + 482 over Finite Field in i of size 883^2
          To:   Elliptic Curve defined by y^2 = x^3 + 320*x + 401 over Finite Field in i of size 883^2
          Via:  (u,r,s,t) = (882*i, 0, 0, 0)
    """
    E = phi.domain()
    if psi.domain() != E:
        raise ValueError('domains do not match')

    isos = phi.codomain().isomorphisms(psi.codomain())
    if not isos:
        raise ValueError('codomains not isomorphic')

    F = E.base_ring()
    from sage.rings.finite_rings import finite_field_base
    from sage.rings.number_field import number_field_base

    if isinstance(F, finite_field_base.FiniteField):
        while len(isos) > 1:
            for _ in range(20):
                P = E.random_point()
                im_phi, im_psi = (phi._eval(P), psi._eval(P))
                isos = [iso for iso in isos if iso._eval(im_phi) == im_psi]
                if len(isos) <= 1:
                    break
            else:
                E = E.base_extend(E.base_field().extension(2, 'U'))  # named extension is faster

    elif isinstance(F, number_field_base.NumberField):
        for _ in range(100):
            P = E.lift_x(F.random_element(), extend=True)
            if P.has_finite_order():
                continue
            break
        else:
            assert False, "couldn't find a point of infinite order"
        im_phi, im_psi = (phi._eval(P), psi._eval(P))
        isos = [iso for iso in isos if iso._eval(im_phi) == im_psi]

    else:
        # fall back to generic method
        sc = psi.scaling_factor() / phi.scaling_factor()
        isos = [iso for iso in isos if iso.u == sc]

    assert len(isos) <= 1
    if isos:
        return isos[0]

    # found no suitable isomorphism -- either doesn't exist or a bug
    raise ValueError('isogenies not equal up to post-isomorphism')
